"use client"

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getApiUrl } from '@/lib/api'
import { followResearch, stageLabels, type Connection, type ReadProblem, type ResearchSnapshot } from '@/lib/research-progress'
import { createClient } from '@/lib/supabase/client'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Bot } from 'lucide-react'

type Stage = keyof typeof stageLabels

export default function ActiveResearchPage() {
  const id = useParams<{ id: string }>().id.toLowerCase()
  const router = useRouter()
  const [attempt, setAttempt] = useState(0)
  const [snapshot, setSnapshot] = useState<ResearchSnapshot | null>(null)
  const [activity, setActivity] = useState<Stage[]>([])
  const [connection, setConnection] = useState<Connection>('connecting')
  const [problem, setProblem] = useState<ReadProblem | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const supabase = createClient()
    setSnapshot(null)
    setActivity([])
    setProblem(null)
    setConnection('connecting')

    const read = async (stream: boolean, signal: AbortSignal) => {
      const { data: { session }, error } = await supabase.auth.getSession()
      if (!session) {
        const unavailable = error?.name === 'AuthRetryableFetchError' || (error?.status ?? 0) >= 500
        return new Response(null, { status: unavailable ? 503 : 401 })
      }
      signal.throwIfAborted()
      const deadline = new AbortController()
      const timer = setTimeout(() => deadline.abort(), 110000)
      try {
        const response = await fetch(getApiUrl(`/research/${encodeURIComponent(id)}${stream ? '/stream' : ''}`), {
          headers: { Authorization: `Bearer ${session.access_token}`, Accept: stream ? 'text/event-stream' : 'application/json' },
          signal: AbortSignal.any([signal, deadline.signal]),
          cache: 'no-store',
        })
        if (stream || !response.ok) return response
        // Keep the deadline active while the JSON body is being downloaded.
        return new Response(await response.text(), { status: response.status })
      } finally {
        clearTimeout(timer)
      }
    }

    void followResearch({
      id, signal: controller.signal, read,
      onSnapshot: session => {
        setSnapshot(session)
        if (session.status === 'completed') router.replace(`/report/${session.id}`)
      },
      onConnection: setConnection,
      onActivity: stage => setActivity(previous => previous.includes(stage) ? previous : [...previous, stage]),
      onProblem: setProblem,
    })
    return () => controller.abort()
  }, [id, attempt, router])

  const status = snapshot?.status
  const terminal = status === 'completed' || status === 'failed' || status === 'cancelled'
  const mode = snapshot?.config?.mode
  const connectionLabel = connection === 'live' ? 'Live updates connected'
    : connection === 'connecting' ? 'Connecting to live updates'
    : 'Live updates interrupted. Checking research status.'

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight mb-2">Research in Progress</h1>
        {snapshot && <p className="text-lg font-medium break-words">{snapshot.question}</p>}
        {mode && <p className="text-secondary">{mode === 'fast' ? 'Fast Research' : 'Deep Research'}</p>}
      </div>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-brand-sage" />
            <CardTitle className="text-lg">Agent Activity</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div role="status" className="space-y-1">
            {status && <p className="font-medium">{stageLabels[status]}</p>}
            {!snapshot && !problem && <p>Loading research session…</p>}
            {snapshot && !terminal && !problem?.terminal && <p className="text-sm text-secondary">{connectionLabel}</p>}
          </div>
          {problem && <p role="alert" className="p-3 bg-status-error/10 text-status-error text-sm rounded-md">{problem.message}</p>}
          {status === 'failed' && <p role="alert" className="text-status-error">{snapshot?.failure_reason || 'Research ended before a report could be generated.'}</p>}
          {activity.length > 0 && (
            <ol aria-label="Received research updates" className="space-y-2 text-sm text-secondary">
              {activity.map(stage => <li key={stage} className="border-b border-border pb-2">{stageLabels[stage]}</li>)}
            </ol>
          )}
          {status === 'completed' && <Button variant="brand" onClick={() => router.replace(`/report/${id}`)}>View report</Button>}
          {problem?.status === 401 && <Button variant="brand" onClick={() => router.push('/login')}>Sign in</Button>}
          {!terminal && (problem && !problem.terminal || !problem?.terminal && connection === 'disconnected') &&
            <Button onClick={() => setAttempt(value => value + 1)}>Reconnect</Button>}
        </CardContent>
      </Card>
    </div>
  )
}
