/** Parse fragmented SSE frames without placing credentials in URLs. */
export async function readResearchStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  onEvent: (event: string, data: Record<string, unknown>) => boolean | void,
): Promise<boolean> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let lastActivity = Date.now()
  const watchdog = setInterval(() => {
    if (Date.now() - lastActivity > 45000) void reader.cancel().catch(() => undefined)
  }, 5000)
  const cancel = () => { void reader.cancel().catch(() => undefined) }
  signal.addEventListener('abort', cancel, { once: true })
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read()
      if (done) return false
      lastActivity = Date.now()
      buffer += decoder.decode(value, { stream: true })
      // Normalize CRLF only once a complete line is available.
      buffer = buffer.replace(/\r\n/g, '\n')
      if (buffer.length > 65536) throw new Error('Oversized stream frame')
      let end: number
      while ((end = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        let event = 'message'
        const data: string[] = []
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
        }
        if (!data.length) continue
        const parsed: unknown = JSON.parse(data.join('\n'))
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Invalid stream event')
        if (onEvent(event, parsed as Record<string, unknown>)) return true
      }
    }
    return false
  } finally {
    clearInterval(watchdog)
    signal.removeEventListener('abort', cancel)
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
