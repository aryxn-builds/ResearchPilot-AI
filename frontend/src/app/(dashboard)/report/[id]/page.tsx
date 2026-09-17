import { createClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ArrowLeft, Calendar, FileText } from 'lucide-react'
import Link from 'next/link'

export default async function ReportPage({ params }: { params: { id: string } }) {
  const supabase = await createClient()

  const { data: session, error } = await supabase
    .from('research_sessions')
    .select('*')
    .eq('id', params.id)
    .single()

  if (error || !session) {
    notFound()
  }

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
              <span>Depth: {session.depth}</span>
            </div>
          </div>

          <div className="prose prose-sage max-w-none prose-headings:font-serif prose-h1:text-brand-sage prose-a:text-brand-sage prose-a:no-underline hover:prose-a:underline">
            {session.report_markdown ? (
              <ReactMarkdown>{session.report_markdown}</ReactMarkdown>
            ) : (
              <p className="text-secondary italic">Report content is not available yet.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
