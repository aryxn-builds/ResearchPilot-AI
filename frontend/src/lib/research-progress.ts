import { readResearchStream } from './research-stream'

export const stageLabels = {
  pending: 'Queued',
  planning: 'Planning the research',
  researching: 'Gathering sources',
  verifying: 'Verifying findings',
  writing: 'Writing the report',
  completed: 'Report complete',
  failed: 'Research failed',
  cancelled: 'Research cancelled',
}

type Status = keyof typeof stageLabels
export type ResearchSnapshot = {
  id: string
  question: string
  status: Status
  config?: { mode?: string }
  failure_reason?: string | null
}

export type Connection = 'connecting' | 'live' | 'disconnected'
export type ReadProblem = { message: string; status?: number; terminal: boolean }

export function describeReadError(status: number) {
  switch (status) {
    case 401: return 'Your session has expired. Sign in to continue.'
    case 403: return 'You do not have access to this research.'
    case 404: return 'This research session could not be found.'
    case 409: return 'This research session is in an invalid state.'
    case 422: return 'This research session ID is invalid.'
    default: return 'The research service could not load the session. Retrying status.'
  }
}

function delay(ms: number, signal: AbortSignal) {
  if (signal.aborted) return Promise.resolve()
  return new Promise<void>(resolve => {
    const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve() }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
  })
}

export async function followResearch({
  id, signal, read, onSnapshot, onConnection, onActivity, onProblem, interval = 4000,
}: {
  id: string
  signal: AbortSignal
  read: (stream: boolean, signal: AbortSignal) => Promise<Response>
  onSnapshot: (snapshot: ResearchSnapshot) => void
  onConnection: (state: Connection) => void
  onActivity: (status: Status) => void
  onProblem: (problem: ReadProblem | null) => void
  interval?: number
}) {
  const streamController = new AbortController()
  const streamSignal = AbortSignal.any([signal, streamController.signal])
  let stream: Promise<void> | null = null

  const connect = async () => {
    onConnection('connecting')
    try {
      const response = await read(true, streamSignal)
      if (!response.ok || !response.body || !response.headers.get('content-type')?.includes('text/event-stream')) return
      if (streamSignal.aborted) return
      onConnection('live')
      await readResearchStream(response.body, streamSignal, (event, data) => {
        if (event === 'done' || event === 'error') return true
        if (event === 'status_update' && (!data.research_id || data.research_id === id) &&
            typeof data.status === 'string' && Object.hasOwn(stageLabels, data.status)) {
          onActivity(data.status as Status)
        }
      })
    } catch {
      // The authoritative session read below continues after a stream failure.
    } finally {
      if (!streamSignal.aborted) onConnection('disconnected')
    }
  }

  try {
    while (!signal.aborted) {
      try {
        const response = await read(false, signal)
        if (signal.aborted) return
        if (!response.ok) {
          const terminal = [401, 403, 404, 409, 422].includes(response.status)
          onProblem({ message: describeReadError(response.status), status: response.status, terminal })
          if (terminal) return
        } else {
          const snapshot = (await response.json()).data as ResearchSnapshot | undefined
          if (signal.aborted) return
          if (!snapshot || snapshot.id !== id || typeof snapshot.question !== 'string' ||
              !Object.hasOwn(stageLabels, snapshot.status)) {
            onProblem({ message: 'The research service returned invalid session details. Retrying status.', terminal: false })
          } else {
            onProblem(null)
            onSnapshot(snapshot)
            if (['completed', 'failed', 'cancelled'].includes(snapshot.status)) return
            stream ??= connect().finally(() => { stream = null })
          }
        }
      } catch {
        if (signal.aborted) return
        onProblem({ message: 'Cannot reach the research service. Retrying status.', terminal: false })
      }
      await delay(interval, signal)
    }
  } finally {
    streamController.abort()
  }
}
