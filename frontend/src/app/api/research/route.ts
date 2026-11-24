import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { getApiUrl } from '@/lib/api'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

const uuidPattern = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i

export async function POST(request: NextRequest) {
  // Cookie authentication makes an exact same-origin check necessary for CSRF.
  if (request.headers.get('origin') !== request.nextUrl.origin) {
    return NextResponse.json({ message: 'Request origin rejected.' }, { status: 403 })
  }
  let payload: unknown
  try { payload = await request.json() } catch {
    return NextResponse.json({ message: 'Enter a valid research question.' }, { status: 422 })
  }
  const key = request.headers.get('idempotency-key')
  if (!key || !uuidPattern.test(key)) {
    return NextResponse.json({ message: 'Invalid submission identifier. Reload the page.' }, { status: 400 })
  }
  const configured = process.env.RESEARCHPILOT_BACKEND_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim()
  if (!configured && process.env.NODE_ENV === 'production') {
    return NextResponse.json({ message: 'Research service is not configured. Please contact support.' }, { status: 503 })
  }
  let endpoint: URL
  try {
    endpoint = new URL(getApiUrl('/research', configured))
    const protocols = process.env.NODE_ENV === 'production' ? ['https:'] : ['http:', 'https:']
    if (endpoint.username || endpoint.password || endpoint.search || endpoint.hash || !protocols.includes(endpoint.protocol)) {
      throw new Error('Invalid backend URL')
    }
  } catch {
    return NextResponse.json({ message: 'Research service configuration is invalid.' }, { status: 503 })
  }

  let accessToken: string
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()
    if (error && (error.name === 'AuthRetryableFetchError' || (error.status ?? 0) >= 500)) throw error
    const { data: { session } } = user && !error
      ? await supabase.auth.getSession()
      : { data: { session: null } }
    if (!session?.access_token) {
      return NextResponse.json({ message: 'Your session has expired. Please sign in again.' }, { status: 401 })
    }
    accessToken = session.access_token
  } catch (error) {
    console.error('research_submission_auth_unavailable', error instanceof Error ? error.name : 'UnknownError')
    return NextResponse.json({ message: 'Sign-in verification is temporarily unavailable. Please retry.' }, { status: 503 })
  }

  const timeout = Number(process.env.RESEARCH_SUBMISSION_TIMEOUT_MS || 120000)
  try {
    const deadline = AbortSignal.timeout(Number.isFinite(timeout) ? Math.max(1000, Math.min(timeout, 150000)) : 120000)
    const upstream = await fetch(endpoint.href, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify(payload),
      cache: 'no-store',
      redirect: 'error',
      signal: request.signal ? AbortSignal.any([request.signal, deadline]) : deadline,
    })
    const body = await upstream.json().catch((error: unknown) => {
      if (error instanceof SyntaxError) return null
      throw error
    })
    const requestId = upstream.headers.get('x-request-id') || body?.meta?.request_id
    const headers = typeof requestId === 'string' && uuidPattern.test(requestId)
      ? { 'X-Request-ID': requestId } : undefined
    if (upstream.ok) {
      const researchId = body?.data?.research_id
      if (typeof researchId === 'string' && uuidPattern.test(researchId)) {
        return NextResponse.json(body, { status: upstream.status, headers })
      }
      console.error('research_submission_invalid_response', { requestId: headers?.['X-Request-ID'], status: upstream.status })
      return NextResponse.json({ message: 'The research service returned an invalid session response. Retry to recover the session.' }, { status: 502, headers })
    }
    if (upstream.status === 422) {
      // Forward field names and validation messages only, never submitted inputs.
      const details = body?.error?.details?.errors || body?.detail
      const fields = Array.isArray(details) ? details.map((item: { loc?: unknown[]; msg?: string }) => ({
        field: (item as { field?: string }).field || item.loc?.slice(-1)[0], message: (item as { message?: string }).message || item.msg,
      })) : []
      return NextResponse.json({ message: 'Check your research question and selected mode.', fields }, { status: 422, headers })
    }
    const status = [400, 401, 403, 409, 429, 500, 502, 503, 504].includes(upstream.status) ? upstream.status : 502
    if (status >= 500) console.error('research_submission_upstream_failure', {
      status: upstream.status, requestId: headers?.['X-Request-ID'],
    })
    const message = status === 401 ? 'Your session has expired. Please sign in again.'
      : status === 403 ? 'You do not have permission to submit this research.'
      : status === 409 && body?.error?.code === 'MAX_SESSIONS_REACHED' ? 'You have reached the active research limit. Try again after a session finishes.'
      : status === 409 ? 'This submission identifier is already in use. Check History.'
      : status === 429 ? 'Research limit reached. Please try again later.'
      : status === 400 ? 'The research service rejected this request. Check your research question and selected mode.'
      : status === 504 ? 'The research service took too long to respond. Retry to recover the session.'
      : status === 503 && body?.error?.code === 'AUTH_UNAVAILABLE' ? 'Sign-in verification is temporarily unavailable. Please retry.'
      : status === 503 && body?.error?.code === 'DATABASE_UNAVAILABLE' ? 'The research database is unavailable. Retry to recover your session.'
      : status === 503 ? 'The research service is unavailable. Retry when it is available.'
      : 'The research service could not confirm your session. Retry to recover it.'
    return NextResponse.json({ message }, { status, headers })
  } catch (error) {
    if (request.signal?.aborted) return new NextResponse(null, { status: 499 })
    const timedOut = error instanceof Error && error.name === 'TimeoutError'
    console.error('research_submission_transport_failure', { timedOut, error: error instanceof Error ? error.name : 'UnknownError' })
    return NextResponse.json({ message: timedOut
      ? 'The research service took too long to respond. Retry to recover the session.'
      : 'The connection to the research service was interrupted. Retry to recover the session.' }, { status: timedOut ? 504 : 503 })
  }
}
