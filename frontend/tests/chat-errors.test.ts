// What the panel says when the server turns a question away.
//
// These drive askViaApi itself, with fetch stubbed, rather than only the two
// helpers: a helper test alone would still pass if the 429 branch were never
// wired into the request path.

import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { askViaApi, ChatError, RESTING, restingMessage, retryAfterOf } from '../src/lib/chat.ts'
import type { SolveRequest, SolveResponse } from '../src/types.ts'

// Mirrors BANNED in backend/app/solver/wording.py. Three frontend files keep
// their own copy of this list; adding a word there means adding it here too.
const BANNED = ['infeasib', 'guarantee']

const REQ = {} as unknown as SolveRequest
const RES = {} as unknown as SolveResponse

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
})

function answering(status: number, body: unknown, headers: Record<string, string> = {}) {
  globalThis.fetch = (() =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json', ...headers },
      }),
    )) as typeof fetch
}

async function ask(): Promise<ChatError> {
  const ctl = new AbortController()
  try {
    await askViaApi([{ role: 'user', text: 'why?' }], REQ, RES, 'server', ctl.signal)
  } catch (e) {
    return e as ChatError
  }
  throw new Error('expected askViaApi to throw')
}

test('a 429 comes back as resting, not as a failure', async () => {
  answering(429, { detail: 'The explainer is resting: too many questions too quickly.' }, { 'Retry-After': '3' })
  const e = await ask()
  assert.equal(e.status, 429)
  assert.match(e.message, /resting/)
  assert.doesNotMatch(e.message, /fail|crash|error/i)
})

test('the seconds from the header are shown', async () => {
  answering(429, { detail: 'x' }, { 'Retry-After': '7' })
  assert.match((await ask()).message, /Try again in 7 seconds\./)
})

test('a 429 with no usable header still reads correctly', async () => {
  answering(429, { detail: 'x' })
  assert.match((await ask()).message, /Try again in a moment\./)

  answering(429, { detail: 'x' }, { 'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT' })
  assert.match((await ask()).message, /Try again in a moment\./)
})

test('the server detail is never echoed on a 429', async () => {
  // The server's own wording is safe; echoing whatever arrives is the habit
  // that put a banned word on screen once before.
  answering(429, { detail: 'nothing here is guaranteed and it is infeasible' }, { 'Retry-After': '3' })
  const message = (await ask()).message.toLowerCase()
  for (const word of BANNED) assert.ok(!message.includes(word), `${word} reached the screen`)
  assert.ok(!message.includes('nothing here'))
})

test('no client message uses a banned word', () => {
  const messages = [RESTING, restingMessage(null), restingMessage(1), restingMessage(42)]
  for (const m of messages) {
    for (const word of BANNED) assert.ok(!m.toLowerCase().includes(word), `${word} in ${m}`)
  }
  assert.match(restingMessage(1), /1 second\./)
  assert.match(restingMessage(2), /2 seconds\./)
})

test('the 502 and 503 branches are unchanged', async () => {
  answering(503, { detail: 'The explainer is off: no Gemini API key is configured on the server.' })
  const off = await ask()
  assert.equal(off.status, 503)
  assert.match(off.message, /no Gemini API key/)

  answering(502, { detail: 'quota exceeded' })
  const upstream = await ask()
  assert.equal(upstream.status, 502)
  assert.equal(upstream.message, 'quota exceeded')
})

test('retryAfterOf reads only a usable number of seconds', () => {
  const of = (h: Record<string, string>) => retryAfterOf(new Response(null, { headers: h }))
  assert.equal(of({ 'Retry-After': '5' }), 5)
  assert.equal(of({ 'Retry-After': ' 5 ' }), 5)
  assert.equal(of({}), null)
  assert.equal(of({ 'Retry-After': '0' }), null)
  assert.equal(of({ 'Retry-After': '-2' }), null)
  assert.equal(of({ 'Retry-After': 'soon' }), null)
})
