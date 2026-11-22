"use client"

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { getApiUrl } from '@/lib/api'
import { readResearchStream } from '@/lib/research-stream'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Loader2, CheckCircle2, ArrowRight, Bot } from 'lucide-react'

type ProgressEvent = {
  status: string
  agent: string
  message: string
}

export default function ActiveResearchPage() {
  const { id } = useParams()
  const router = useRouter()
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [isComplete, setIsComplete] = useState(false)
  const [mode, setMode] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [terminal, setTerminal] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (startedAt === null || terminal) return
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [startedAt, terminal])

  useEffect(() => {
    const controller = new AbortController()
    const handle = (event: string, data: Record<string, unknown>) => {
      if (controller.signal.aborted) return
      if (event === 'done' || event === 'error') {
        setTerminal(true)
        if (typeof data.elapsed_seconds === 'number') setElapsed(Math.floor(data.elapsed_seconds))
        if (data.status === 'completed') setIsComplete(true)
        else setError(typeof data.failure_reason === 'string' ? data.failure_reason : 'Research ended without a completed report.')
        return true
      }
      if (event === 'status_update' && typeof data.status === 'string') {
        if (typeof data.mode === 'string') setMode(data.mode)
        if (typeof data.created_at === 'string') setStartedAt(Date.parse(data.created_at))
        setEvents(previous => {
          if (previous.at(-1)?.status === data.status) return previous
          return [...previous.slice(-49), { status: String(data.status), agent: 'System', message: `Status updated to ${data.status}` }]
        })
      }
      return false
    }
    setEvents([])
    setError(null)
    setTerminal(false)
    setIsComplete(false)
    setMode(null)
    setStartedAt(null)
    setElapsed(0)

    const run = async () => {
      for (let attempt = 0; attempt < 3; attempt++) {
        if (controller.signal.aborted) return
        try {
          const supabase = createClient()
          const { data: { session } } = await supabase.auth.getSession()
          if (controller.signal.aborted) return
          if (!session) { router.replace('/login'); return }
          const response = await fetch(getApiUrl(`/research/${id}/stream`), {
            headers: { Authorization: `Bearer ${session.access_token}`, Accept: 'text/event-stream' },
            signal: controller.signal, cache: 'no-store',
          })
          if ([401, 403, 404].includes(response.status)) {
            setError('Research unavailable. Check your session and access permissions.')
            setTerminal(true)
            return
          }
          if (!response.ok || !response.body) throw new Error('Stream unavailable')
          if (await readResearchStream(response.body, controller.signal, handle)) return
        } catch {
          if (controller.signal.aborted) return
        }
        if (attempt < 2) {
          await new Promise<void>(resolve => {
            const finish = () => { clearTimeout(timer); controller.signal.removeEventListener('abort', finish); resolve() }
            const timer = setTimeout(finish, 1000 * (attempt + 1))
            controller.signal.addEventListener('abort', finish, { once: true })
          })
        }
      }
      if (!controller.signal.aborted) {
        setError('Live updates disconnected after three attempts. Reload to reconnect.')
        setTerminal(true)
      }
    }
    void run()
    return () => controller.abort()
  }, [id, router])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight mb-2">Research in Progress</h1>
        <p className="text-secondary">{mode ? (mode === 'fast' ? 'Fast Research' : 'Deep Research') : 'Research'}
          {startedAt !== null && Number.isFinite(elapsed) ? ` ? ${elapsed}s elapsed` : ''}</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-brand-sage" />
              <CardTitle className="text-lg">Agent Activity</CardTitle>
            </div>
            {isComplete ? (
              <span className="flex items-center gap-2 text-status-success text-sm font-semibold">
                <CheckCircle2 className="h-4 w-4" /> Completed
              </span>
            ) : terminal ? null : (
              <span className="flex items-center gap-2 text-brand-sage text-sm font-semibold">
                <Loader2 className="h-4 w-4 animate-spin" /> Processing
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-status-error/10 text-status-error text-sm rounded-md">
              {error}
            </div>
          )}
          
          <div role="log" aria-label="Research activity" className="bg-foreground rounded-lg p-4 font-mono text-sm text-secondary h-[400px] overflow-y-auto flex flex-col gap-2">
            {events.length === 0 && !error && !isComplete && (
              <div className="text-center mt-10">Initializing agents...</div>
            )}
            
            {events.map((evt, idx) => (
              <div key={idx} className="flex flex-col border-b border-white/10 pb-2 last:border-0">
                <span className="text-brand-sage font-semibold uppercase text-xs">[{evt.agent}]</span>
                <span className="text-white/90">{evt.message}</span>
              </div>
            ))}
          </div>

          {isComplete && (
            <div className="mt-6 flex justify-end">
              <Button variant="brand" className="gap-2" onClick={() => router.push(`/report/${id}`)}>
                View Generated Report <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
