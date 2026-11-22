const { test } = require('node:test')
const assert = require('node:assert/strict')
const Module = require('node:module')
const original = Module._load
let authenticated = true
Module._load = function(name, ...args) {
 if (name === '@/lib/supabase/server') return { createClient: async () => ({ auth: {
  getUser: async () => ({data:{user: authenticated ? {id:'user'} : null}}),
  getSession: async () => ({data:{session: authenticated ? {access_token:'private-token'} : null}})
 }}) }
 if (name === '@/lib/api') return {getApiUrl: () => 'https://backend.example/api/v1/research'}
 return original.call(this, name, ...args)
}
const { POST } = require('../scratch/submission/app/api/research/route.js')
process.env.RESEARCHPILOT_BACKEND_URL = 'https://backend.example'
function request(mode='fast', origin='https://app.example') {
 return {headers: new Headers({origin,'idempotency-key':'11111111-1111-1111-1111-111111111111'}),
 nextUrl: new URL('https://app.example/api/research'),
 json: async () => ({question:'What is RAG?',config:{mode}})}
}
test('submission proxy mode, auth, status and network cases', async () => {
 for (const mode of ['fast','deep']) {
  let calls = 0
  global.fetch = async (url, options) => {
   calls++; assert.equal(url,'https://backend.example/api/v1/research')
   assert.equal(JSON.parse(options.body).config.mode, mode)
   assert.equal(options.headers.Authorization,'Bearer private-token')
   return Response.json({data:{research_id:'id'}},{status:202})
  }
  assert.equal((await POST(request(mode))).status,202)
  assert.equal(calls,1)
 }
 authenticated=false
 assert.equal((await POST(request())).status,401)
 authenticated=true
 assert.equal((await POST(request('fast','https://attacker.example'))).status,403)
 for (const status of [401,429,503]) {
  global.fetch=async()=>Response.json({}, {status})
  assert.equal((await POST(request())).status,status)
 }
 for (const [error,status] of [[new TypeError('network'),503],[new DOMException('timeout','TimeoutError'),504]]) {
  let calls=0
  global.fetch=async()=>{calls++;throw error}
  assert.equal((await POST(request())).status,status)
  assert.equal(calls,1)
 }
 global.fetch=async()=>Response.json({error:{details:{errors:[{field:'mode',message:'Invalid mode'}]}}},{status:422})
 const result=await POST(request('unsupported'))
 assert.equal(result.status,422)
 assert.equal((await result.json()).fields[0].message,'Invalid mode')
})
