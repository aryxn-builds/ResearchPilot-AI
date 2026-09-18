"use client"

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { createClient } from '@/lib/supabase/client'
import { getApiUrl } from '@/lib/api'
import { Bot, Loader2 } from 'lucide-react'

export default function NewResearchPage() {
  const router = useRouter()
  const [topic, setTopic] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) return

    setLoading(true)
    setError(null)
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()

    if (!session) {
      router.push('/login')
      return
    }

    try {
      const response = await fetch(getApiUrl('/research'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          question: topic
        })
      })

      if (!response.ok) {
        throw new Error('Failed to start research')
      }

      const data = await response.json()
      
      // Redirect to the active research view
      const researchId = data?.data?.research_id || data?.research_id || data?.id;
      router.push(`/research/active/${researchId}`)
    } catch (err: Error | unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('An unexpected error occurred')
      }
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
                onChange={(e) => setTopic(e.target.value)}
                required
              />
            </div>
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
