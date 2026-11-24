"use client"

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Bot, Loader2 } from 'lucide-react'

export default function NewResearchPage() {
  const router = useRouter()
  const pending = useRef(false)
  const submission = useRef<AbortController | null>(null)
  const keys = useRef(new Map<string, string>())
  const errorRef = useRef<HTMLDivElement>(null)
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<'deep' | 'fast'>('deep')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { if (error) errorRef.current?.focus() }, [error])
  useEffect(() => () => submission.current?.abort(), [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pending.current || topic.trim().length < 10) return
    pending.current = true

    setLoading(true)
    setError(null)
    const controller = new AbortController()
    submission.current = controller
    // Let the proxy's deadline expire first so it can return a useful error.
    const timer = setTimeout(() => controller.abort(), 185000)
    let navigating = false
    try {
      const payload = JSON.stringify({ question: topic.trim(), config: { mode } })
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(payload))
      const storageKey = 'research-submission:' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
      let key = keys.current.get(storageKey)
      if (!key) {
        try { key = sessionStorage.getItem(storageKey) ?? undefined } catch { /* Storage may be disabled. */ }
        key ??= crypto.randomUUID()
        keys.current.set(storageKey, key)
        try { sessionStorage.setItem(storageKey, key) } catch { /* The in-memory key still protects this page. */ }
      }
      const response = await fetch('/api/research', {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': key,
        },
        body: payload,
      })

      const data = await response.json().catch((error: unknown) => {
        if (error instanceof SyntaxError) return null
        throw error
      })
      if (!response.ok) {
        const fields = Array.isArray(data?.fields) ? data.fields.map((field: { field?: string; message?: string }) => `${field.field || 'Question'}: ${field.message || 'Invalid value'}`).join(' ') : ''
        throw new Error(fields || data?.message || 'The research service could not confirm your session. Retry to recover it.')
      }

      const researchId = data?.data?.research_id
      if (typeof researchId !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(researchId)) {
        throw new Error('The research service returned an invalid session response. Retry to recover the session.')
      }
      router.push(`/research/active/${researchId}`)
      navigating = true
      keys.current.delete(storageKey)
      try { sessionStorage.removeItem(storageKey) } catch { /* Navigation can proceed without storage. */ }
    } catch (err: unknown) {
      setError(err instanceof DOMException && err.name === 'AbortError'
        ? 'The service took too long to respond. Retry to recover the session.'
        : err instanceof TypeError ? 'The connection was interrupted. Retry to recover the session.'
        : err instanceof Error ? err.message : 'The research service could not confirm your session. Retry to recover it.')
    } finally {
      clearTimeout(timer)
      submission.current = null
      if (!navigating) {
        pending.current = false
        setLoading(false)
      }
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight mb-2">New Research</h1>
        <p className="text-secondary">Define a topic and deploy an autonomous agent to gather and synthesize information.</p>
      </div>

      <Card>
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <div className="flex items-center gap-2 mb-2">
              <Bot className="h-5 w-5 text-brand-sage" />
              <CardTitle className="text-lg">Research Configuration</CardTitle>
            </div>
            <CardDescription>
              Be specific about what you want to research to get better results.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {error && (
              <div ref={errorRef} role="alert" tabIndex={-1} className="p-3 bg-status-error/10 text-status-error text-sm rounded-md">
                {error}
              </div>
            )}
            
            <div className="space-y-2">
              <label htmlFor="topic" className="text-sm font-medium">
                Research Topic or Question
              </label>
              <Input
                id="topic"
                placeholder="e.g., What are the latest advancements in solid-state batteries?"
                value={topic}
                onChange={(e) => { setTopic(e.target.value); setError(null) }}
                disabled={loading}
                minLength={10}
                maxLength={1000}
                required
              />
            </div>
            <fieldset disabled={loading} className="space-y-2">
              <legend className="text-sm font-medium">Research mode</legend>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" name="mode" value="deep" checked={mode === 'deep'}
                    onChange={() => { setMode('deep'); setError(null) }} />
                  Deep Research
                </label>
                <label className="flex items-center gap-2">
                  <input type="radio" name="mode" value="fast" checked={mode === 'fast'}
                    onChange={() => { setMode('fast'); setError(null) }} />
                  Fast Research
                </label>
              </div>
            </fieldset>
          </CardContent>
          <CardFooter className="bg-surface/50 border-t border-border flex justify-end">
            <Button variant="brand" type="submit" disabled={loading || topic.trim().length < 10}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deploying Agent...
                </>
              ) : (
                error ? 'Retry Research' : 'Start Research'
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
