import test from 'node:test'
import assert from 'node:assert/strict'
import { followResearch } from '../scratch/research-progress.js'

const id = '79d64b7b-98db-4e7f-884d-536ae562cf12'
function snapshot(status) {
  return Response.json({data: {id, question: 'what is GPT?', status, config: {mode: 'fast'}}})
}

test('stream EOF reconnects and a persisted report ends recovery', async () => {
  const states = []
  const activity = []
  const connection = []
  let streams = 0
  const controller = new AbortController()
  await followResearch({
    id, signal: controller.signal, interval: 1,
    read: async (stream, signal) => {
      if (!stream) return snapshot(streams < 2 ? 'researching' : 'completed')
      streams++
      const headers = {'Content-Type': 'text/event-stream'}
      if (streams === 1) return new Response('event: status_update\ndata: {"status":"researching"}\n\n', {headers})
      return new Response(new ReadableStream({
        start(streamController) {
          signal.addEventListener('abort', () => streamController.close(), {once: true})
        },
      }), {headers})
    },
    onSnapshot: value => states.push(value),
    onActivity: value => activity.push(value),
    onConnection: value => connection.push(value),
    onProblem: value => assert.equal(value, null),
  })
  assert.equal(streams, 2)
  assert.equal(states[0].question, 'what is GPT?')
  assert.equal(states.at(-1).status, 'completed')
  assert.deepEqual(activity, ['researching'])
  assert.ok(connection.includes('disconnected'))
})

test('reloading a completed session uses persisted state without opening a stream', async () => {
  let result
  await followResearch({
    id, signal: new AbortController().signal,
    read: async stream => { assert.equal(stream, false); return snapshot('completed') },
    onSnapshot: value => { result = value },
    onActivity: assert.fail, onConnection: assert.fail,
    onProblem: value => assert.equal(value, null),
  })
  assert.equal(result.status, 'completed')
})

for (const [status, label] of [[401, /expired/], [403, /access/], [404, /found/], [409, /state/], [422, /invalid/]]) {
  test(`status ${status} stops reads and reports a specific cause`, async () => {
    let problem
    await followResearch({
      id, signal: new AbortController().signal,
      read: async stream => { assert.equal(stream, false); return new Response(null, {status}) },
      onSnapshot: assert.fail, onActivity: assert.fail, onConnection: assert.fail,
      onProblem: value => { problem = value },
    })
    assert.equal(problem.terminal, true)
    assert.match(problem.message, label)
  })
}
