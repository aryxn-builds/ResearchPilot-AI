"use client"

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
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
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let isMounted = true;

    const setupSSE = async () => {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()

      if (!session) {
        if (isMounted) router.push('/login')
        return
      }

      // Fetch the token and use it if SSE on the backend requires auth.
      // Wait, standard EventSource doesn't support custom headers easily, so we usually pass token in query param or rely on cookies.
      // Assuming the backend SSE endpoint can authenticate via query param or doesn't need auth for the stream if it's protected otherwise,
      // Actually, standard EventSource doesn't support headers. If backend needs it, we append it as a query param.
      
      const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/research/${id}/stream`)
      url.searchParams.append('token', session.access_token)

      eventSource = new EventSource(url.toString())

      eventSource.onmessage = (event) => {
        if (!isMounted) return
        
        try {
          const data = JSON.parse(event.data)
          if (data.status === 'completed') {
            setIsComplete(true)
            eventSource?.close()
          } else {
            setEvents((prev) => [...prev, data])
          }
        } catch (err) {
          console.error("Failed to parse SSE data", err)
        }
      }

      eventSource.onerror = (err) => {
        console.error("SSE Error:", err)
        if (isMounted) {
          setError("Connection to research agent lost.")
          eventSource?.close()
        }
      }
    }

    setupSSE()

    return () => {
      isMounted = false
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [id, router])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight mb-2">Research in Progress</h1>
        <p className="text-secondary">Your autonomous agent is working. This may take a few minutes.</p>
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
            ) : (
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
          
          <div className="bg-foreground rounded-lg p-4 font-mono text-sm text-secondary h-[400px] overflow-y-auto flex flex-col gap-2">
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
