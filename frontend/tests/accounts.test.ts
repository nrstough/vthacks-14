// Building requests from a loaded account, and saying on screen where it came
// from. Both are pure, so both are tested here rather than through the page.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CANDIDATE_LIMIT,
  REASON_ORDER,
  REASON_TEXT,
  chatKey,
  parseAccount,
  provenanceLine,
  sliderBounds,
  toBase,
  toCandidatesRequest,
} from '../src/lib/accounts.ts'
import { SCENARIOS } from '../src/fixtures/scenarios.ts'
import { solve } from '../src/solver/mockSolver.ts'
import type { Candidate, LoadedAccount, NessieAccountResponse, ScheduledTxn } from '../src/types.ts'

const scheduled: ScheduledTxn[] = [
  { id: 'n_a', date: '2026-09-20', description: 'KROGER #382', amount_cents: -6400, kind: 'discretionary', recurring: false },
  { id: 'n_b', date: '2026-09-25', description: 'HARRIS TEETER PAYROLL', amount_cents: 31200, kind: 'income', recurring: true },
]

const modelled: LoadedAccount = {
  seed: 12345,
  as_of: '2026-09-19',
  horizon_end: '2026-10-18',
  opening_balance_cents: 19892,
  buffer_cents: 2500,
  scheduled,
  source: 'modelled',
}

function nessie(over: Partial<NessieAccountResponse> = {}): NessieAccountResponse {
  return {
    seed: 20260919,
    as_of: '2026-09-19',
    horizon_end: '2026-10-18',
    opening_balance_cents: 49800,
    buffer_cents: 2500,
    scheduled,
    source: 'nessie',
    nessie: { customer_id: 'cust_0', account_id: 'abc123def456', mode: 'seeded' },
    written: 23,
    returned: 23,
    not_round_tripped: [],
    ...over,
  }
}

// ---- building the two requests ----

test('the candidates request carries only the fields that endpoint declares', () => {
  // Spreading the account would carry seed and source, and the endpoint forbids
  // extras, so the whole call would 422.
  const req = toCandidatesRequest(modelled)
  assert.deepEqual(Object.keys(req).sort(), ['as_of', 'horizon_end', 'limit', 'scheduled'])
  assert.equal(req.limit, 18)
})

test('the candidate limit stays where every fallback can still answer', () => {
  // The server's exhaustive engine refuses above 18 and the browser's above 20.
  assert.equal(CANDIDATE_LIMIT, 18)
})

test('the solve request carries only the fields that endpoint declares', () => {
  const req = toBase(modelled, [])
  assert.deepEqual(
    Object.keys(req).sort(),
    ['as_of', 'buffer_cents', 'candidates', 'horizon_end', 'locks', 'opening_balance_cents', 'scheduled'],
  )
})

test('a freshly loaded account carries no overrides', () => {
  // Carrying them would name candidate ids this account has never heard of,
  // which is a 422 on the whole solve rather than a missing row.
  assert.deepEqual(toBase(modelled, []).locks, { in: [], out: [] })
})

// ---- provenance ----

test('an account whose origin cannot be named is refused', () => {
  assert.throws(() => parseAccount({ source: 'my bank', scheduled: [] }), /provenance/)
  assert.throws(() => parseAccount(null), /provenance/)
  assert.throws(() => parseAccount({}), /provenance/)
})

test('a recognised account is passed through', () => {
  assert.equal(parseAccount(modelled).source, 'modelled')
  assert.equal(parseAccount(nessie()).source, 'nessie')
})

test('the built-in account names itself and its window', () => {
  const line = provenanceLine(null, SCENARIOS[0].request)
  assert.equal(line, 'Sample checking account, Sep 19 to Oct 2.')
})

test('a modelled account names its seed, so it can be regenerated', () => {
  assert.equal(
    provenanceLine(modelled, toBase(modelled, [])),
    'Modelled account, seed 12345, Sep 19 to Oct 18.',
  )
})

test('a clean sandbox round trip says so', () => {
  const account = nessie()
  assert.equal(
    provenanceLine(account, toBase(account, [])),
    'Capital One sandbox, 23 of 23 rows read back, Sep 19 to Oct 18.',
  )
})

test('one changed amount reads in the singular', () => {
  const account = nessie({
    not_round_tripped: [{ id: 'n_a', reason: 'amount changed by the sandbox' }],
  })
  assert.match(provenanceLine(account, toBase(account, [])), /1 amount changed by the sandbox/)
})

test('three changed amounts read in the plural', () => {
  const account = nessie({
    not_round_tripped: [
      { id: 'n_a', reason: 'amount changed by the sandbox' },
      { id: 'n_b', reason: 'amount changed by the sandbox' },
      { id: 'n_c', reason: 'amount changed by the sandbox' },
    ],
  })
  assert.match(provenanceLine(account, toBase(account, [])), /3 amounts changed by the sandbox/)
})

test('each reason is counted separately and in a fixed order', () => {
  // "3 rows changed" would be false when one was dropped, one was undated and
  // one was moved. They have different causes and different fixes.
  const account = nessie({
    not_round_tripped: [
      { id: 'n_d', reason: 'outside the window' },
      { id: 'n_c', reason: 'no usable date' },
      { id: 'n_b', reason: 'amount changed by the sandbox' },
      { id: 'n_a', reason: 'written but not returned' },
    ],
  })
  assert.equal(
    provenanceLine(account, toBase(account, [])),
    'Capital One sandbox, 23 of 23 rows read back, 1 row not returned, ' +
      '1 amount changed by the sandbox, 1 row without a date, 1 row outside the window, ' +
      'Sep 19 to Oct 18.',
  )
})

test('a read-only sandbox account does not claim a round trip it did not do', () => {
  const account = nessie({
    written: 0,
    returned: 2,
    nessie: { customer_id: 'cust_0', account_id: 'abc123def456', mode: 'read_only' },
  })
  const line = provenanceLine(account, toBase(account, []))
  assert.match(line, /Capital One sandbox account def456, 2 rows/)
  assert.doesNotMatch(line, /read back/)
})

test('no provenance line breaks the wording rules', () => {
  const lines = [
    provenanceLine(null, SCENARIOS[0].request),
    provenanceLine(modelled, toBase(modelled, [])),
    provenanceLine(nessie(), toBase(nessie(), [])),
  ]
  for (const line of lines) {
    assert.doesNotMatch(line, /guarantee/i)
    assert.doesNotMatch(line, /infeasib/i)
    assert.doesNotMatch(line, /real bank/i)
  }
})

test('a read-only account still reports what it could not use', () => {
  // The combination read-only mode actually produces: no write comparison, but
  // rows the sandbox returned undated or outside the window.
  const account = nessie({
    written: 0,
    returned: 1,
    nessie: { customer_id: 'cust_0', account_id: 'abc123def456', mode: 'read_only' },
    not_round_tripped: [
      { id: 'n_a', reason: 'no usable date' },
      { id: 'n_b', reason: 'outside the window' },
      { id: 'n_c', reason: 'outside the window' },
    ],
  })
  assert.equal(
    provenanceLine(account, toBase(account, [])),
    'Capital One sandbox account def456, 2 rows, 1 row without a date, ' +
      '2 rows outside the window, Sep 19 to Oct 18.',
  )
})

// ---- the explainer's conversation belongs to one account ----

test('each account gets its own chat identity', () => {
  // The key remounts the panel: a conversation must never span two accounts,
  // and a pending reply about the old one must not land under the new one.
  assert.equal(chatKey(null), 'preset')
  assert.equal(chatKey(modelled), 'm12345')
  assert.equal(chatKey(nessie()), 'abc123def456')
})

test('two accounts of the same source still remount the explainer', () => {
  assert.notEqual(chatKey({ ...modelled, seed: 1 }), chatKey({ ...modelled, seed: 2 }))
  const a = nessie()
  const b = nessie({ nessie: { ...a.nessie, account_id: 'zzz999' } })
  assert.notEqual(chatKey(a), chatKey(b))
})

test('leaving an account for a preset remounts the explainer', () => {
  assert.notEqual(chatKey(nessie()), chatKey(null))
  assert.notEqual(chatKey(modelled), chatKey(null))
})

// ---- the slider grid ----

test('a loaded balance lands on the slider grid', () => {
  // A range input snaps its value to min + k*step, so an off-grid balance
  // renders with the thumb elsewhere and jumps on the first drag.
  for (const opening of [19892, 20000, 45000, 500, 0, 49800, 2137]) {
    const { min, max } = sliderBounds(opening)
    assert.equal((opening - min) % 500, 0, `opening ${opening} off grid`)
    assert.equal((max - min) % 500, 0, `max for ${opening} off grid`)
    assert.ok(min <= opening && opening <= max, `opening ${opening} outside [${min}, ${max}]`)
  }
})

test('the usual range is unchanged for an on-grid balance', () => {
  assert.deepEqual(sliderBounds(20000), { min: 2000, max: 30000 })
})

test('a balance above the usual ceiling raises it', () => {
  assert.ok(sliderBounds(45000).max >= 45000)
})

test('a balance below the usual floor lowers it', () => {
  assert.equal(sliderBounds(500).min, 500)
  assert.equal(sliderBounds(0).min, 0)
})

// ---- the offline fallback ----

test('a loaded account still solves on the built-in solver', () => {
  // Venue wifi dies and the page falls back. An account loaded before that
  // happens is in memory and must still produce an answer.
  const account: LoadedAccount = {
    ...modelled,
    scheduled: SCENARIOS[0].request.scheduled,
  }
  const res = solve(toBase(account, SCENARIOS[0].request.candidates), [])
  assert.ok(res.tier >= 1 && res.tier <= 3)
})

test('more than twenty actionable changes is what the limit exists to prevent', () => {
  // Documents why CANDIDATE_LIMIT is 18: the stand-in is exhaustive and refuses
  // above 20, and it would throw inside the solve effect's catch.
  const many: Candidate[] = Array.from({ length: 21 }, (_, i) => ({
    id: `c_${i}`,
    label: `Change ${i}`,
    detail: 'x',
    action: 'skip',
    target_txn_id: `t_${i}`,
    freed_cents: 100,
    effective_date: '2026-09-20',
    recharge_date: null,
    lead_time_days: 0,
    pain: 1,
  }))
  const req = toBase(
    {
      ...modelled,
      scheduled: many.map((_c, i) => ({
        id: `t_${i}`,
        date: '2026-09-20',
        description: 'KROGER #382',
        amount_cents: -100,
        kind: 'discretionary' as const,
        recurring: false,
      })),
    },
    many,
  )
  assert.throws(() => solve(req, []), /under 20/)
  assert.ok(many.length > CANDIDATE_LIMIT)
})

test('every reason the server can send has words and a place in the order', () => {
  // The backend gained a fifth reason and this file did not, so the clause was
  // dropped from the sentence in silence — the exact failure not_round_tripped
  // exists to prevent. REASON_TEXT is a Record now, so the compiler catches a
  // missing word; this catches a missing position in the order.
  const account = nessie({
    not_round_tripped: REASON_ORDER.map((reason, i) => ({ id: `n_${i}`, reason })),
  })
  const line = provenanceLine(account, toBase(account, []))
  // One of each, so each reason contributes exactly one singular clause.
  for (const reason of REASON_ORDER) {
    const [singular] = REASON_TEXT[reason]
    assert.ok(line.includes(`1 ${singular}`), `${reason} is missing from: ${line}`)
  }
  assert.match(line, /too small for the sandbox to hold/)
})
