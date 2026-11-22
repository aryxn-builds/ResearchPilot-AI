'use client'
import { Button } from '@/components/ui/Button'
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <div role="alert" className="space-y-4"><p>Could not load this page. Check your connection and try again.</p><Button onClick={reset}>Try again</Button></div>
}
