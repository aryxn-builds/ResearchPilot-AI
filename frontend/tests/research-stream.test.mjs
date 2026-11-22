import test from 'node:test'
import assert from 'node:assert/strict'
import { readResearchStream } from '../scratch/research-stream.js'
const encoder = new TextEncoder()
function body(parts) {
  return new ReadableStream({ start(controller) {
    for (const part of parts) controller.enqueue(encoder.encode(part))
    controller.close()
  } })
}
test('fragmented frames deliver status and terminal once', async () => {
  const events = []
  assert.equal(await readResearchStream(body([
    'event: status_update\r', '\ndata: {"status":"planning"}\r\n\r\n',
    'event: done\ndata: {"status":"completed"}\n\n'
  ]), new AbortController().signal, (event, data) => {
    events.push([event, data.status]); return event === 'done'
  }), true)
  assert.deepEqual(events, [['status_update','planning'],['done','completed']])
})
test('EOF and invalid payload are handled', async () => {
  assert.equal(await readResearchStream(body([': heartbeat\n\n']), new AbortController().signal, () => {}), false)
  await assert.rejects(readResearchStream(body(['data: []\n\n']), new AbortController().signal, () => {}))
})
test('abort suppresses delivery', async () => {
  const c = new AbortController(); c.abort()
  let calls = 0
  await readResearchStream(body(['data: {}\n\n']), c.signal, () => { calls++ })
  assert.equal(calls, 0)
})
