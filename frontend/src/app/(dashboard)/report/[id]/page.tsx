"use client"

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { getApiUrl } from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  ArrowLeft,
  BookOpen,
  Calendar,
  ExternalLink,
  FileText,
  Globe,
  Loader2,
} from 'lucide-react'
import Link from 'next/link'

interface CitationDetail {
  source_id?: string
  url?: string
  title?: string | null
}

interface SourceDetail {
  id: string
  url: string
  title: string
  domain?: string
}

export interface ReferenceItem {
  marker: string
  number: number
  title: string
  url: string
  domain?: string
  source_id?: string
}

interface ReportData {
  session: {
    id: string
    status: string
    research_question: string | null
    config: { depth?: string } | null
    created_at: string
  }
  prose_content: string | null
  references: ReferenceItem[]
}

function buildReferenceList(
  citationMap: Record<string, unknown> | null,
  sources: SourceDetail[],
  rawMarkdown: string
): { references: ReferenceItem[]; uuidToNumber: Map<string, number> } {
  const refMap = new Map<number, ReferenceItem>()
  const uuidToNumber = new Map<string, number>()
  let nextAssignNumber = 1

  // 1. Process citation_map (supports both new [1] markers and legacy UUID keys)
  if (citationMap && typeof citationMap === 'object') {
    Object.entries(citationMap).forEach(([marker, val]) => {
      const cleanMarker = marker.trim().replace(/^\[|\]$/g, '')
      let num = 0
      if (/^\d+$/.test(cleanMarker)) {
        num = parseInt(cleanMarker, 10)
      } else {
        num = nextAssignNumber++
      }

      uuidToNumber.set(cleanMarker.toLowerCase(), num)

      let url = ''
      let title = ''
      let sourceId = ''

      if (typeof val === 'string') {
        sourceId = val
        uuidToNumber.set(val.toLowerCase(), num)
        const matchedSource = sources.find((s) => s.id.toLowerCase() === val.toLowerCase())
        if (matchedSource) {
          url = matchedSource.url
          title = matchedSource.title
        }
      } else if (val && typeof val === 'object') {
        const detail = val as CitationDetail
        url = detail.url || ''
        title = detail.title || ''
        sourceId = detail.source_id || ''
        if (sourceId) {
          uuidToNumber.set(sourceId.toLowerCase(), num)
        }
      }

      let domain = ''
      if (url) {
        try {
          domain = new URL(url).hostname.replace(/^www\./, '')
        } catch {
          domain = ''
        }
      }

      refMap.set(num, {
        marker: `[${num}]`,
        number: num,
        title: title.trim() || domain || url || `Source ${num}`,
        url,
        domain,
        source_id: sourceId,
      })
    })
  }

  // 2. Parse from raw markdown references section if any exist
  const entryRegex =
    /(?:^|\n)\s*(?:\[?(\d+)\]?\.?|\d+\.)\s*([^\n]+?)\s*(?:\n\s*\[?(https?:\/\/[^\s)\]]+)\]?(?:\([^\)]+\))?|\s*[-—–]\s*\[?(https?:\/\/[^\s)\]]+)\]?(?:\([^\)]+\))?)/gi

  let match: RegExpExecArray | null
  while ((match = entryRegex.exec(rawMarkdown)) !== null) {
    const num = parseInt(match[1], 10)
    let title = match[2]?.trim().replace(/^[-—–:\s]+|[-—–:\s]+$/g, '')
    const url = match[3] || match[4]
    if (num > 0 && url) {
      let domain = ''
      try {
        domain = new URL(url).hostname.replace(/^www\./, '')
      } catch {
        domain = ''
      }

      if (!title || title === url) {
        title = domain || url
      }

      if (!refMap.has(num) || !refMap.get(num)?.url) {
        refMap.set(num, {
          marker: `[${num}]`,
          number: num,
          title,
          url,
          domain,
        })
      }
    }
  }

  // 3. Fallback to sources table if still empty
  if (refMap.size === 0 && sources && sources.length > 0) {
    sources.forEach((src, idx) => {
      const num = idx + 1
      let domain = src.domain || ''
      if (!domain && src.url) {
        try {
          domain = new URL(src.url).hostname.replace(/^www\./, '')
        } catch {
          domain = ''
        }
      }
      uuidToNumber.set(src.id.toLowerCase(), num)
      refMap.set(num, {
        marker: `[${num}]`,
        number: num,
        title: src.title || src.url,
        url: src.url,
        domain,
        source_id: src.id,
      })
    })
  }

  // Map any matching sources by URL
  sources.forEach((src) => {
    refMap.forEach((ref) => {
      if (ref.url && src.url && ref.url.toLowerCase() === src.url.toLowerCase()) {
        uuidToNumber.set(src.id.toLowerCase(), ref.number)
      }
    })
  })

  return {
    references: Array.from(refMap.values()).sort((a, b) => a.number - b.number),
    uuidToNumber,
  }
}

function linkifyCitationsAndUrls(
  markdown: string,
  uuidToNumber: Map<string, number>
): string {
  // Separate trailing ## References so references are cleanly presented in the dedicated list
  let prose = markdown
  const refIndex = markdown.search(/(?:^|\n)##\s+References/i)
  if (refIndex !== -1) {
    prose = markdown.substring(0, refIndex).trim()
  }

  const uuidPattern = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/

  // Transform citations [1], [2], [1, 2] or legacy [f69cfed8-...] into clickable links [[1]](#ref-1)
  // Negative lookahead (?!\() prevents matching existing markdown links [text](url)
  prose = prose.replace(/\[([^\]]+)\](?!\()/g, (fullMatch, content) => {
    // If content contains UUIDs
    if (uuidPattern.test(content)) {
      const uuids = content.match(new RegExp(uuidPattern.source, 'gi')) || []
      const resolvedNums: number[] = []
      for (const u of uuids) {
        const num = uuidToNumber.get(u.toLowerCase())
        if (num && !resolvedNums.includes(num)) {
          resolvedNums.push(num)
        }
      }
      if (resolvedNums.length > 0) {
        resolvedNums.sort((a, b) => a - b)
        return resolvedNums.map((n) => `[[${n}]](#ref-${n})`).join(', ')
      }
      return ''
    }

    // Check if content is purely citation numbers: e.g. "1" or "1, 2" or "1, 2, 3"
    if (/^\d+(?:\s*,\s*\d+)*$/.test(content.trim())) {
      const numbers = content.split(',').map((s: string) => s.trim())
      return numbers.map((n: string) => `[[${n}]](#ref-${n})`).join(', ')
    }

    return fullMatch
  })

  // Convert bare URLs into clickable markdown links if not already wrapped
  prose = prose.replace(/(^|[\s(])(https?:\/\/[^\s)<>]+)/g, '$1[$2]($2)')

  return prose
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
      const {
        data: { session },
      } = await supabase.auth.getSession()

      if (!session) {
        router.push('/login')
        return
      }

      try {
        // Fetch session metadata via Supabase
        const { data: sessionData, error: sessionError } = await supabase
          .from('research_sessions')
          .select('id, status, research_question, config, created_at')
          .eq('id', id)
          .single()

        if (sessionError || !sessionData) {
          setError('Report not found or you do not have access.')
          setLoading(false)
          return
        }

        // Fetch report content from the backend API using Bearer token
        const reportRes = await fetch(getApiUrl(`/research/${id}/report`), {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        })

        let markdownContent: string | null = null
        let citationMap: Record<string, unknown> | null = null
        if (reportRes.ok) {
          const reportJson = await reportRes.json()
          markdownContent =
            reportJson.data?.content_markdown ?? reportJson.data?.markdown_content ?? null
          citationMap = reportJson.data?.citation_map ?? null
        }

        // Also fetch sources from Supabase for completeness
        const { data: sourcesData } = await supabase
          .from('sources')
          .select('id, url, title, domain')
          .eq('session_id', id)

        const { references, uuidToNumber } = buildReferenceList(
          citationMap,
          (sourcesData as SourceDetail[]) || [],
          markdownContent || ''
        )

        const proseContent = markdownContent
          ? linkifyCitationsAndUrls(markdownContent, uuidToNumber)
          : null

        setData({
          session: sessionData,
          prose_content: proseContent,
          references,
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

  const { session, prose_content, references } = data

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

      <Card className="border-border bg-surface shadow-sm">
        <CardContent className="p-6 sm:p-10">
          <div className="border-b border-border pb-6 mb-8">
            <div className="flex items-center gap-2 mb-4 text-brand-sage">
              <FileText className="h-5 w-5" />
              <span className="font-semibold uppercase tracking-wider text-xs">
                Generated Research Report
              </span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold font-serif tracking-tight mb-4 text-foreground">
              {session.research_question || 'Untitled Report'}
            </h1>
            <div className="flex flex-wrap items-center gap-4 text-sm text-secondary">
              <span className="flex items-center gap-1.5">
                <Calendar className="h-4 w-4" />
                {new Date(session.created_at).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
              <span>•</span>
              <span>Depth: {session.config?.depth || 'Standard'}</span>
              {references.length > 0 && (
                <>
                  <span>•</span>
                  <span>
                    {references.length} {references.length === 1 ? 'Reference' : 'References'}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Report Prose with Clickable Citations */}
          <div className="prose prose-sage max-w-none prose-headings:font-serif prose-h1:text-brand-sage prose-a:text-brand-sage prose-a:no-underline hover:prose-a:underline">
            {prose_content ? (
              <ReactMarkdown
                urlTransform={(url) => {
                  try {
                    const parsed = new URL(url, 'https://researchpilot.local')
                    if (['http:', 'https:', 'mailto:', 'tel:'].includes(parsed.protocol)) {
                      return url
                    }
                    return ''
                  } catch {
                    return ''
                  }
                }}
                components={{
                  a: ({ href, children, ...props }) => {
                    // Handle inline citation links that point to references
                    if (href?.startsWith('#ref-')) {
                      const refNum = href.replace('#ref-', '')
                      return (
                        <a
                          href={href}
                          title={`Jump to Reference [${refNum}]`}
                          className="inline text-brand-sage font-mono font-bold px-1 py-0.5 rounded hover:bg-brand-sage/15 transition-all text-xs align-super no-underline cursor-pointer select-none focus:outline-none focus:ring-2 focus:ring-brand-sage"
                          onClick={(e) => {
                            e.preventDefault()
                            const targetId = href.substring(1)
                            const elem = document.getElementById(targetId)
                            if (elem) {
                              elem.scrollIntoView({ behavior: 'smooth', block: 'center' })
                              elem.classList.add('ring-2', 'ring-brand-sage', 'bg-brand-sage/10')
                              setTimeout(() => {
                                elem.classList.remove('ring-2', 'ring-brand-sage', 'bg-brand-sage/10')
                              }, 2500)
                            }
                          }}
                        >
                          {children}
                        </a>
                      )
                    }

                    // Standard external link
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-sage underline decoration-brand-sage/40 hover:decoration-brand-sage font-medium inline-flex items-center gap-1 break-all"
                        {...props}
                      >
                        {children}
                        <ExternalLink className="h-3 w-3 inline shrink-0" />
                      </a>
                    )
                  },
                }}
              >
                {prose_content}
              </ReactMarkdown>
            ) : (
              <p className="text-secondary italic">Report content is not available yet.</p>
            )}
          </div>

          {/* Structured References List */}
          {references.length > 0 && (
            <div className="mt-12 pt-8 border-t border-border" id="references-section">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2 text-brand-sage">
                  <BookOpen className="h-5 w-5" />
                  <h2 className="text-xl font-bold font-serif text-foreground">
                    References & Sources
                  </h2>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  {references.length} {references.length === 1 ? 'Source' : 'Sources'}
                </Badge>
              </div>

              <div className="space-y-3">
                {references.map((ref) => (
                  <div
                    key={ref.marker}
                    id={`ref-${ref.number}`}
                    className="p-4 rounded-lg border border-border bg-surface/60 hover:bg-surface hover:border-brand-sage/50 transition-all duration-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3 group"
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <span className="shrink-0 px-2.5 py-1 rounded bg-brand-sage/10 text-brand-sage font-mono font-bold text-xs mt-0.5 border border-brand-sage/20">
                        {ref.marker}
                      </span>
                      <div className="min-w-0 space-y-1">
                        {ref.url ? (
                          <a
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-foreground hover:text-brand-sage hover:underline line-clamp-1 inline-flex items-center gap-1.5 text-sm"
                          >
                            {ref.title}
                            <ExternalLink className="h-3.5 w-3.5 text-secondary group-hover:text-brand-sage shrink-0" />
                          </a>
                        ) : (
                          <span className="font-medium text-foreground text-sm line-clamp-1">
                            {ref.title}
                          </span>
                        )}

                        <div className="flex items-center gap-2 text-xs text-secondary">
                          {ref.domain && (
                            <span className="inline-flex items-center gap-1 bg-accent-light px-2 py-0.5 rounded text-secondary font-sans text-[11px]">
                              <Globe className="h-3 w-3" />
                              {ref.domain}
                            </span>
                          )}
                          {ref.url && (
                            <a
                              href={ref.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="truncate hover:text-brand-sage hover:underline font-mono text-[11px]"
                            >
                              {ref.url}
                            </a>
                          )}
                        </div>
                      </div>
                    </div>

                    {ref.url && (
                      <div className="shrink-0 pt-2 sm:pt-0">
                        <a
                          href={ref.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block w-full sm:w-auto"
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5 text-xs w-full sm:w-auto hover:bg-brand-sage hover:text-white transition-colors"
                          >
                            Open Link <ExternalLink className="h-3 w-3" />
                          </Button>
                        </a>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
