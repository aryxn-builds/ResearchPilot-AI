"use client"

import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { createClient } from '@/lib/supabase/client'
import { getApiUrl } from '@/lib/api'
import { Bot, Loader2 } from 'lucide-react'

export default function NewResearchPage() {
  const router = useRouter()
  const pending = useRef(false)
  const key = useRef<string | null>(null)
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<'deep' | 'fast'>('deep')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pending.current || topic.trim().length < 10) return
    pending.current = true
    key.current ??= crypto.randomUUID()

    setLoading(true)
    setError(null)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 30000)
    try {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()

    if (!session) {
      router.push('/login')
      return
    }

      const response = await fetch(getApiUrl('/research'), {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': key.current,
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          question: topic,
          config: { mode }
        })
      })

      if (!response.ok) {
        throw new Error(response.status === 429 ? 'Research limit reached. Try again later.' : 'Could not start research. Check your connection and try again.')
      }

      const data = await response.json()
      
      // Redirect to the active research view
      const researchId = data?.data?.research_id || data?.research_id || data?.id;
      if (typeof researchId !== "string" || !/^[0-9a-f-]{36}$/i.test(researchId)) throw new Error("Invalid session response. Check History before retrying.")
      router.push(`/research/active/${researchId}`)
    } catch (err: Error | unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('An unexpected error occurred')
      }
    } finally {
      clearTimeout(timer)
      pending.current = false
      setLoading(false)
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
              <div className="p-3 bg-status-error/10 text-status-error text-sm rounded-md">
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
                onChange={(e) => { setTopic(e.target.value); key.current = null }}
                minLength={10}
                maxLength={1000}
                disabled={loading}
                required
              />
            </div>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Research mode</legend>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" name="mode" value="deep" checked={mode === 'deep'}
                    onChange={() => setMode('deep')} />
                  Deep Research
                </label>
                <label className="flex items-center gap-2">
                  <input type="radio" name="mode" value="fast" checked={mode === 'fast'}
                    onChange={() => setMode('fast')} />
                  Fast Research
                </label>
              </div>
            </fieldset>
          </CardContent>
          <CardFooter className="bg-surface/50 border-t border-border flex justify-end">
            <Button variant="brand" type="submit" disabled={loading || !topic.trim()}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deploying Agent...
                </>
              ) : (
                'Start Research'
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
