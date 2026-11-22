import { Skeleton } from '@/components/ui/Skeleton'
export default function Loading() {
  return <div role="status" aria-label="Loading page" className="max-w-5xl space-y-6"><Skeleton className="h-10 w-64" /><Skeleton className="h-40 w-full" /><span className="sr-only">Loading page?</span></div>
}
