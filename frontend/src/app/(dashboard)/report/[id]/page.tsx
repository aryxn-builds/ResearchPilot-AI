"use client"

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import ReactMarkdown from 'react-markdown'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ArrowLeft, Calendar, FileText, Loader2 } from 'lucide-react'
import Link from 'next/link'

interface ReportData {
  session: {
    id: string
    status: string
    research_question: string | null
    config: { depth?: string } | null
    created_at: string
  }
  markdown_content: string | null
}

export default function ReportPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchReport = async () => {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()

      if (!session) {
        router.push('/login')
        return
      }

      try {
        // Fetch session metadata via Supabase (client-side, uses anon key with JWT)
        const { data: sessionData, error: sessionError } = await supabase
          .from('research_sessions')
          .select('id, status, research_question, config, created_at')
          .eq('id', id)
          .single()

        if (sessionError || !sessionData) {
          console.error("DEBUG: sessionError =", sessionError)
          setError('Report not found or you do not have access.')
          setLoading(false)
          return
        }

        // Fetch report content from the backend API using Bearer token
        const apiUrl = process.env.NEXT_PUBLIC_API_URL
        console.log("DEBUG: apiUrl =", apiUrl)
        console.log(`DEBUG: fetching ${apiUrl}/research/${id}/report`)
        
        const reportRes = await fetch(`${apiUrl}/research/${id}/report`, {
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
          },
        })
        console.log("DEBUG: reportRes status =", reportRes.status)

        let markdownContent: string | null = null
        if (reportRes.ok) {
          const reportJson = await reportRes.json()
          markdownContent = reportJson.data?.content_markdown ?? reportJson.data?.markdown_content ?? null
        }

        setData({
          session: sessionData,
          markdown_content: markdownContent,
        })
      } catch {
        setError('Failed to load report. Please try again.')
      } finally {
        setLoading(false)
      }
    }

    fetchReport()
  }, [id, router])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-brand-sage" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="h-4 w-4" /> Back to Dashboard
          </Button>
        </Link>
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-status-error">{error ?? 'Report not found.'}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { session, markdown_content } = data

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="h-4 w-4" /> Back to Dashboard
          </Button>
        </Link>
        <div className="flex gap-2">
          <Badge variant={session.status === 'completed' ? 'success' : 'warning'}>
            {session.status}
          </Badge>
        </div>
      </div>

      <Card>
        <CardContent className="p-8">
          <div className="border-b border-border pb-6 mb-8">
            <div className="flex items-center gap-2 mb-4 text-brand-sage">
              <FileText className="h-5 w-5" />
              <span className="font-semibold uppercase tracking-wider text-sm">Generated Research Report</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold font-serif tracking-tight mb-4">
              {session.research_question || 'Untitled Report'}
            </h1>
            <div className="flex items-center gap-4 text-sm text-secondary">
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {new Date(session.created_at).toLocaleDateString()}
              </span>
              <span>•</span>
              <span>Depth: {session.config?.depth || 'Standard'}</span>
            </div>
          </div>

          <div className="prose prose-sage max-w-none prose-headings:font-serif prose-h1:text-brand-sage prose-a:text-brand-sage prose-a:no-underline hover:prose-a:underline">
            {markdown_content ? (
              <ReactMarkdown>{markdown_content}</ReactMarkdown>
            ) : (
              <p className="text-secondary italic">Report content is not available yet.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
