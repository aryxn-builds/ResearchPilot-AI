import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { FileText, Clock, Plus, ArrowLeft } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export const dynamic = 'force-dynamic'

export default async function HistoryPage({ searchParams }: { searchParams: { page?: string } }) {
  const page = Math.max(1, Math.min(10000, Number.parseInt(searchParams.page || "1", 10) || 1))
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Fetch all research sessions for the authenticated user (Rule S-03 user isolation)
  const { data: sessions, error } = await supabase
    .from('research_sessions')
    .select('id, research_question, status, created_at, iteration_count, total_claims')
    .is('deleted_at', null)
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .order('id', { ascending: false })
    .range((page - 1) * 20, page * 20 - 1)

  const completedCount = sessions?.filter((s) => s.status === 'completed').length || 0

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="gap-1.5 text-secondary hover:text-foreground">
                <ArrowLeft className="h-4 w-4" /> Back to Dashboard
              </Button>
            </Link>
          </div>
          <h1 className="text-3xl font-bold font-serif tracking-tight text-foreground">
            Research History
          </h1>
          <p className="text-secondary text-sm">
            Review past autonomous investigations and generated reports.
          </p>
        </div>

        <Link href="/research/new">
          <Button variant="brand" className="gap-2">
            <Plus className="h-4 w-4" /> New Research
          </Button>
        </Link>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card className="border-border bg-surface shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-secondary">Investigations on this page</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground font-serif">{sessions?.length || 0}</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-surface shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-secondary">Completed on this page</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-brand-sage font-serif">{completedCount}</div>
          </CardContent>
        </Card>
      </div>

      <nav aria-label="History pages" className="flex gap-6 text-sm">
        {page > 1 && <Link href={`?page=${page - 1}`}>Previous</Link>}
        <span>Page {page}</span>
        {sessions?.length === 20 && <Link href={`?page=${page + 1}`}>Next</Link>}
      </nav>
      {/* Session List */}
      <div className="space-y-4">
        {error && (
          <div className="rounded-md bg-status-error/10 border border-status-error/20 p-4 text-sm text-status-error">
            Failed to load research history. Please refresh the page.
          </div>
        )}

        {!error && (!sessions || sessions.length === 0) ? (
          <Card className="border-dashed border-border bg-surface">
            <CardContent className="p-12 text-center flex flex-col items-center">
              <FileText className="h-12 w-12 text-border mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-1 font-serif">No research sessions yet</h3>
              <p className="text-secondary text-sm mb-6 max-w-sm">
                Start your first autonomous research task to generate structured reports with verifiable citations.
              </p>
              <Link href="/research/new">
                <Button variant="brand" className="gap-2">
                  <Plus className="h-4 w-4" /> Start Research
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">
            {sessions?.map((session) => (
              <Card
                key={session.id}
                className="hover:border-brand-sage/50 transition-colors border-border bg-surface shadow-sm"
              >
                <CardContent className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={session.status === 'completed' ? `/report/${session.id}` : `/research/active/${session.id}`}
                        className="font-semibold text-base text-foreground hover:text-brand-sage hover:underline underline-offset-4 line-clamp-1"
                      >
                        {session.research_question || 'Untitled Research'}
                      </Link>
                      <Badge
                        variant={
                          session.status === 'completed'
                            ? 'success'
                            : session.status === 'failed'
                            ? 'error'
                            : 'warning'
                        }
                      >
                        {session.status}
                      </Badge>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-secondary">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDistanceToNow(new Date(session.created_at), { addSuffix: true })}
                      </span>
                      {session.iteration_count !== undefined && session.iteration_count !== null && (
                        <span>• Iterations: {session.iteration_count}</span>
                      )}
                      {session.total_claims !== undefined && session.total_claims !== null && (
                        <span>• Claims: {session.total_claims}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Link href={session.status === 'completed' ? `/report/${session.id}` : `/research/active/${session.id}`}>
                      <Button variant="outline" size="sm" className="w-full sm:w-auto">
                        {session.status === 'completed' ? 'View Report' : 'View Status'}
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
