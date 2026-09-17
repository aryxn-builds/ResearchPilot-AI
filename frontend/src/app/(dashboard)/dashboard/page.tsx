import { createClient } from '@/lib/supabase/server'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { FileText, ArrowRight, Clock, Plus } from 'lucide-react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'

export default async function DashboardPage() {
  const supabase = await createClient()
  
  // Fetch user's research history
  const { data: researchSessions } = await supabase
    .from('research_sessions')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(10)

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight mb-2">Welcome back</h1>
        <p className="text-secondary">Here is an overview of your recent research activities.</p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-brand-sage text-white border-transparent">
          <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
            <div>
              <h3 className="text-xl font-bold mb-1">Start New Research</h3>
              <p className="text-brand-sage/20 text-white/80">Deploy an autonomous agent to research any topic and generate a comprehensive report.</p>
            </div>
            <Link href="/research/new">
              <Button className="w-fit bg-white text-brand-sage hover:bg-white/90 gap-2 font-semibold">
                <Plus className="h-4 w-4" /> Configure Agent
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Stats Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-secondary">Total Reports</span>
              <span className="font-bold text-xl">{researchSessions?.length || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-secondary">Avg. Processing Time</span>
              <span className="font-bold text-xl">~2.5 min</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent History */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold tracking-tight">Recent Reports</h2>
          <Link href="/dashboard/history">
            <Button variant="link" className="gap-1">
              View all <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
        
        <div className="grid gap-4">
          {!researchSessions || researchSessions.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="p-8 text-center flex flex-col items-center">
                <FileText className="h-10 w-10 text-border mb-4" />
                <h3 className="text-lg font-medium mb-1">No research yet</h3>
                <p className="text-secondary mb-4">Start your first autonomous research task.</p>
                <Link href="/research/new">
                  <Button variant="outline">New Research</Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            researchSessions.map((session) => (
              <Card key={session.id} className="hover:border-brand-sage/50 transition-colors">
                <CardContent className="p-4 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Link href={`/report/${session.id}`} className="font-semibold text-lg hover:underline decoration-brand-sage underline-offset-4">
                        {session.research_question || 'Untitled Research'}
                      </Link>
                      <Badge variant={session.status === 'completed' ? 'success' : session.status === 'failed' ? 'error' : 'warning'}>
                        {session.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-secondary">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDistanceToNow(new Date(session.created_at), { addSuffix: true })}
                      </span>
                    </div>
                  </div>
                  <Link href={`/report/${session.id}`}>
                    <Button variant="outline" size="sm" className="shrink-0 w-full sm:w-auto">
                      View Report
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
