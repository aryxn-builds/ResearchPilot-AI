import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { getApiUrl } from '@/lib/api'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

export async function POST(request: NextRequest) {
  // Cookie authentication makes an exact same-origin check necessary for CSRF.
  if (request.headers.get('origin') !== request.nextUrl.origin) {
    return NextResponse.json({ message: 'Request origin rejected.' }, { status: 403 })
  }
  const supabase = await createClient()
  const { data: { user }, error } = await supabase.auth.getUser()
  const { data: { session } } = await supabase.auth.getSession()
  if (error || !user || !session) {
    return NextResponse.json({ message: 'Your session has expired. Please sign in again.' }, { status: 401 })
  }
  let payload: unknown
  try { payload = await request.json() } catch {
    return NextResponse.json({ message: 'Enter a valid research question.' }, { status: 422 })
  }
  const key = request.headers.get('idempotency-key')
  if (!key || !/^[0-9a-f-]{36}$/i.test(key)) {
    return NextResponse.json({ message: 'Invalid submission identifier. Reload the page.' }, { status: 400 })
  }
  const timeout = Number(process.env.RESEARCH_SUBMISSION_TIMEOUT_MS || 120000)
  try {
    const configured = process.env.RESEARCHPILOT_BACKEND_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim()
    if (!configured && process.env.NODE_ENV === 'production') {
      return NextResponse.json({ message: 'Research service is not configured. Please contact support.' }, { status: 503 })
    }
    const endpoint = configured
      ? configured.replace(/\/+$/, '').replace(/(?:\/api\/v1)+$/, '') + '/api/v1/research'
      : getApiUrl('/research')
    const parsed = new URL(endpoint)
    if (parsed.username || parsed.password || parsed.search || parsed.hash ||
      (process.env.NODE_ENV === 'production' && parsed.protocol !== 'https:')) {
      return NextResponse.json({ message: 'Research service configuration is invalid.' }, { status: 503 })
    }
    const upstream = await fetch(endpoint, {
      method: 'POST',
      headers: { Authorization: `Bearer ${session.access_token}`,
        'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify(payload),
      cache: 'no-store',
      signal: AbortSignal.timeout(Number.isFinite(timeout) ? Math.max(1000, Math.min(timeout, 150000)) : 120000),
    })
    const body = await upstream.json().catch(() => null)
    if (upstream.ok && body) return NextResponse.json(body, { status: upstream.status })
    if (upstream.status === 422) {
      // Forward field names and validation messages only, never submitted inputs.
      const details = body?.error?.details?.errors || body?.detail
      const fields = Array.isArray(details) ? details.map((item: { loc?: unknown[]; msg?: string }) => ({
        field: (item as { field?: string }).field || item.loc?.slice(-1)[0], message: (item as { message?: string }).message || item.msg,
      })) : []
      return NextResponse.json({ message: 'Check your research question and selected mode.', fields }, { status: 422 })
    }
    const status = [401, 403, 409, 429].includes(upstream.status) ? upstream.status : 503
    return NextResponse.json({ message: status === 401 ? 'Your session has expired. Please sign in again.'
      : status === 429 ? 'Research limit reached. Please try again later.'
      : status === 409 ? 'A matching research request already exists. Check History.'
      : 'Research service is temporarily unavailable. Please retry.' }, { status })
  } catch (error) {
    const timedOut = error instanceof Error && ['TimeoutError', 'AbortError'].includes(error.name)
    return NextResponse.json({ message: timedOut
      ? 'The service took too long to respond. Check History before retrying this request.'
      : 'Unable to connect to the research service. Check History before retrying.' }, { status: timedOut ? 504 : 503 })
  }
}
