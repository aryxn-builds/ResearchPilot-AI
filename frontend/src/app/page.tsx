import { Button } from "@/components/ui/Button";
import Link from "next/link";
import { ArrowRight, Bot, Search, FileText } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex h-16 items-center justify-between px-6 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-brand-sage" />
          <span className="text-xl font-bold font-serif text-brand-sage tracking-tight">ResearchPilot AI</span>
        </div>
        <nav className="flex items-center gap-4">
          <Link href="/login">
            <Button variant="ghost">Sign In</Button>
          </Link>
          <Link href="/signup">
            <Button variant="brand">Get Started</Button>
          </Link>
        </nav>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center text-center px-4 sm:px-6 lg:px-8 py-24">
        <div className="max-w-3xl space-y-8">
          <h1 className="text-5xl sm:text-6xl font-bold font-serif tracking-tight text-foreground text-balance">
            Autonomous multi-agent research and report generation
          </h1>
          <p className="text-xl text-secondary max-w-2xl mx-auto text-balance">
            Deploy intelligent agents to independently plan, search, synthesize, and draft comprehensive research reports on any topic.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link href="/signup">
              <Button variant="brand" size="lg" className="w-full sm:w-auto text-lg gap-2">
                Start Researching <ArrowRight className="h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-32 max-w-5xl w-full text-left">
          <div className="space-y-4 p-6 rounded-xl border border-border bg-surface">
            <div className="h-12 w-12 rounded-lg bg-accent-light flex items-center justify-center text-brand-sage">
              <Search className="h-6 w-6" />
            </div>
            <h3 className="text-xl font-semibold">Autonomous Research</h3>
            <p className="text-secondary">Agents autonomously plan search strategies and gather high-quality sources.</p>
          </div>
          <div className="space-y-4 p-6 rounded-xl border border-border bg-surface">
            <div className="h-12 w-12 rounded-lg bg-accent-light flex items-center justify-center text-brand-sage">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="text-xl font-semibold">Critical Analysis</h3>
            <p className="text-secondary">Extracted evidence is rigorously critiqued by verification agents for accuracy.</p>
          </div>
          <div className="space-y-4 p-6 rounded-xl border border-border bg-surface">
            <div className="h-12 w-12 rounded-lg bg-accent-light flex items-center justify-center text-brand-sage">
              <FileText className="h-6 w-6" />
            </div>
            <h3 className="text-xl font-semibold">Synthesized Reports</h3>
            <p className="text-secondary">Beautiful, comprehensive markdown reports with full citations.</p>
          </div>
        </div>
      </main>

      <footer className="border-t border-border bg-surface py-8 text-center text-secondary text-sm">
        <p>&copy; {new Date().getFullYear()} ResearchPilot AI. All rights reserved.</p>
      </footer>
    </div>
  );
}
