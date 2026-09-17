import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { Bot, Home, FileText, Settings, LogOut, Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { logout } from '@/app/auth/actions'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-border bg-surface flex flex-col hidden md:flex">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-brand-sage" />
            <span className="font-serif font-bold text-lg text-brand-sage">ResearchPilot</span>
          </Link>
        </div>
        
        <div className="p-4 flex-1 flex flex-col gap-1">
          <Link href="/research/new">
            <Button variant="brand" className="w-full justify-start gap-2 mb-4">
              <Plus className="h-4 w-4" />
              New Research
            </Button>
          </Link>
          
          <div className="text-xs font-semibold text-secondary uppercase tracking-wider mb-2 mt-4 px-2">Menu</div>
          <Link href="/dashboard" className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent-light text-foreground transition-colors">
            <Home className="h-4 w-4 text-secondary" />
            Dashboard
          </Link>
          <Link href="/dashboard/history" className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent-light text-secondary transition-colors">
            <FileText className="h-4 w-4" />
            History
          </Link>
          <Link href="/dashboard/settings" className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent-light text-secondary transition-colors">
            <Settings className="h-4 w-4" />
            Settings
          </Link>
        </div>

        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3 mb-4 px-2">
            <div className="h-8 w-8 rounded-full bg-accent-light flex items-center justify-center text-brand-sage font-semibold text-sm">
              {user.email?.charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-medium truncate">{user.email}</span>
            </div>
          </div>
          <form action={logout}>
            <Button variant="ghost" className="w-full justify-start gap-2 text-status-error hover:text-status-error hover:bg-status-error/10">
              <LogOut className="h-4 w-4" />
              Log out
            </Button>
          </form>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Mobile Header */}
        <header className="h-16 flex items-center justify-between px-4 border-b border-border bg-surface md:hidden">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-brand-sage" />
            <span className="font-serif font-bold text-lg text-brand-sage">ResearchPilot</span>
          </Link>
          <Link href="/research/new">
            <Button variant="brand" size="sm">New</Button>
          </Link>
        </header>

        <div className="flex-1 overflow-y-auto p-6 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
