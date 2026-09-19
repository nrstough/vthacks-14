// Parsing a bank export (A1). Money is string arithmetic here, so the tests
// are about exact cents and about what is REPORTED rather than dropped.

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { MAX_ROWS, MIN_ROWS, parseAmountCents, parseBankCsv, parseDateIso, splitCsv } from '../src/lib/importCsv.ts'

const HEADER = '"DATE","DESCRIPTION","AMOUNT","CHECK #","STATUS"'

function csv(...lines: string[]): string {
  return [HEADER, ...lines].join('\n')
}

// Enough rows to clear MIN_ROWS, so a test about ONE row's handling is not
// really a test about the minimum-history rule.
function padded(...lines: string[]): string {
  const filler = Array.from(
    { length: MIN_ROWS },
    (_unused, i) => `"01/${String(10 + i).padStart(2, '0')}/2026","FILLER CO","-1.00","","Posted"`,
  )
  return csv(...lines, ...filler)
}

test('every amount format a bank writes becomes exact cents', () => {
  assert.equal(parseAmountCents('-9.99'), -999)
  assert.equal(parseAmountCents('19.99'), 1999)
  assert.equal(parseAmountCents('1,234.56'), 123456)
  assert.equal(parseAmountCents('$12.00'), 1200)
  assert.equal(parseAmountCents('(12.00)'), -1200)
  assert.equal(parseAmountCents('($1,234.56)'), -123456)
  assert.equal(parseAmountCents('7'), 700)
  assert.equal(parseAmountCents('.5'), 50)
  assert.equal(parseAmountCents('+3.25'), 325)
})

test('nineteen ninety-nine is never one cent short', () => {
  // The float route gives 1998.9999999999998, and Math.round hides it until
  // the one input where it does not.
  for (let dollars = 0; dollars < 200; dollars++) {
    for (const fraction of ['00', '01', '05', '10', '29', '33', '50', '99']) {
      const text = `${dollars}.${fraction}`
      assert.equal(parseAmountCents(text), dollars * 100 + Number(fraction), text)
    }
  }
})

test('an amount it cannot read is refused, never guessed at', () => {
  assert.equal(parseAmountCents(''), 'bad')
  assert.equal(parseAmountCents('abc'), 'bad')
  assert.equal(parseAmountCents('1.2.3'), 'bad')
  assert.equal(parseAmountCents('1e5'), 'bad')
  assert.equal(parseAmountCents('12.345'), 'decimals')
})

test('dates are validated by component, not normalised into another month', () => {
  assert.equal(parseDateIso('09/16/2026'), '2026-09-16')
  assert.equal(parseDateIso('2026-09-16'), '2026-09-16')
  assert.equal(parseDateIso('9/6/26'), '2026-09-06')
  assert.equal(parseDateIso('9/6/99'), '1999-09-06')
  assert.equal(parseDateIso('02/29/2028'), '2028-02-29')
  // new Date('2026-02-30') rolls into March rather than failing.
  assert.equal(parseDateIso('02/30/2026'), null)
  assert.equal(parseDateIso('04/31/2026'), null)
  assert.equal(parseDateIso('13/01/2026'), null)
  assert.equal(parseDateIso('not a date'), null)
})

test('the header may be in any order or case', () => {
  const filler = Array.from(
    { length: MIN_ROWS },
    (_unused, i) => `-1.00,Posted,01/${String(10 + i).padStart(2, '0')}/2026,FILLER CO`,
  ).join('\n')
  const out = parseBankCsv(`amount,Status,date,DESCRIPTION\n-25.00,Posted,01/02/2026,KROGER\n${filler}`)
  assert.equal(out.error, null)
  assert.deepEqual(out.rows[0], { date: '2026-01-02', description: 'KROGER', amount_cents: -2500 })
})

test('a file missing a column it needs says so', () => {
  const out = parseBankCsv('date,description\n01/02/2026,KROGER')
  assert.match(out.error ?? '', /Date, Description and Amount/)
})

test('quoted fields may contain commas and doubled quotes', () => {
  const table = splitCsv('a,"b,c","d""e"\n1,2,3')
  assert.deepEqual(table[0], ['a', 'b,c', 'd"e'])
})

test('rows that are not posted are excluded and counted', () => {
  const out = parseBankCsv(
    padded('"01/02/2026","KROGER","-25.00","","Posted"', '"01/03/2026","KROGER","-30.00","","Pending"'),
  )
  assert.equal(out.rows.length, MIN_ROWS + 1)
  assert.equal(out.notPosted, 1)
})

test('an unreadable row is reported by line, never silently dropped and never zeroed', () => {
  const out = parseBankCsv(
    padded('"01/02/2026","KROGER","banana","","Posted"', '"02/30/2026","KROGER","-1.00","","Posted"'),
  )
  assert.equal(out.rows.length, MIN_ROWS)
  assert.deepEqual(out.rejected, [
    { line: 2, reason: 'bad_amount' },
    { line: 3, reason: 'bad_date' },
  ])
})

test('a rejection never carries the cell it rejected', () => {
  // The reason codes are a closed set; a message quoting the row would put a
  // private payee into the UI and into anything that logs it.
  const out = parseBankCsv(padded('"01/02/2026","ZZQ7K4 SECRET PAYEE","banana","","Posted"'))
  assert.equal(JSON.stringify(out.rejected).includes('ZZQ7K4'), false)
})

test('a zero-amount row is refused rather than planned around', () => {
  const out = parseBankCsv(padded('"01/02/2026","KROGER","0.00","","Posted"'))
  assert.deepEqual(out.rejected, [{ line: 2, reason: 'zero_amount' }])
})

test('duplicate rows are kept, because two coffees are two coffees', () => {
  const line = '"01/02/2026","STARBUCKS","-4.75","","Posted"'
  const out = parseBankCsv(padded(line, line))
  assert.equal(out.rows.filter((r) => r.amount_cents === -475).length, 2)
})

test('an empty file and a header-only file each say what is wrong', () => {
  assert.match(parseBankCsv('').error ?? '', /empty/)
  assert.match(parseBankCsv(HEADER).error ?? '', /no transactions/)
})

test('a handful of transactions is not a history', () => {
  // A one-row file used to parse fine, plan an empty schedule, and have the
  // solver answer "sufficient" over a single transaction.
  const one = parseBankCsv(csv('"01/02/2026","KROGER","-25.00","","Posted"'))
  assert.match(one.error ?? '', /1 usable transaction; not enough history/)
  assert.equal(one.rows.length, 0)

  const few = parseBankCsv(
    csv(...Array.from({ length: MIN_ROWS - 1 }, (_u, i) => `"01/0${(i % 9) + 1}/2026","KROGER","-1.00","","Posted"`)),
  )
  assert.match(few.error ?? '', /not enough history/)

  const enough = parseBankCsv(
    csv(...Array.from({ length: MIN_ROWS }, (_u, i) => `"01/${String(10 + i).padStart(2, '0')}/2026","KROGER","-1.00","","Posted"`)),
  )
  assert.equal(enough.error, null)
  assert.equal(enough.rows.length, MIN_ROWS)
})

test('a file over the row cap is refused before anything is sent', () => {
  const line = '"01/02/2026","KROGER","-1.00","","Posted"'
  const out = parseBankCsv(csv(...Array(MAX_ROWS + 1).fill(line)))
  assert.match(out.error ?? '', /limit is 20000/)
  assert.equal(out.rows.length, 0)
})

test('a file at exactly the cap is accepted', () => {
  const line = '"01/02/2026","KROGER","-1.00","","Posted"'
  const out = parseBankCsv(csv(...Array(MAX_ROWS).fill(line)))
  assert.equal(out.error, null)
  assert.equal(out.rows.length, MAX_ROWS)
})

test('a real-shaped export parses end to end', () => {
  const out = parseBankCsv(
    padded(
      '"09/16/2026","HARRIS TEETER PAYROLL","1,240.55","","Posted"',
      '"09/15/2026","OAKWOOD PROPERTIES","(1,200.00)","","Posted"',
      '"09/14/2026","DOORDASH*CHIPOTLE","-31.80","","Posted"',
    ),
  )
  assert.equal(out.error, null)
  assert.deepEqual(out.rows.slice(0, 3).map((r) => r.amount_cents), [124055, -120000, -3180])
})

test('a blank status in a file that has a status column is not posted', () => {
  // Planning around money that may never leave is the wrong direction to
  // guess in, so a blank cell is excluded and counted rather than assumed.
  const out = parseBankCsv(
    padded('"01/02/2026","KROGER","-25.00","",""', '"01/03/2026","KROGER","-30.00","","Posted"'),
  )
  assert.equal(out.notPosted, 1)
  assert.equal(out.rows.some((r) => r.amount_cents === -2500), false)
  assert.equal(out.rows.some((r) => r.amount_cents === -3000), true)
})

test('a file with no status column keeps every row', () => {
  const filler = Array.from(
    { length: MIN_ROWS },
    (_u, i) => `01/${String(10 + i).padStart(2, '0')}/2026,FILLER CO,-1.00`,
  ).join('\n')
  const out = parseBankCsv(`date,description,amount\n01/02/2026,KROGER,-25.00\n${filler}`)
  assert.equal(out.error, null)
  assert.equal(out.notPosted, 0)
  assert.equal(out.rows.length, MIN_ROWS + 1)
})

test('malformed money is refused, never silently turned into usable money', () => {
  // Each of these used to parse. The last is the worst: parentheses already
  // mean negative, so a sign inside them made an OUTFLOW into an INFLOW.
  assert.equal(parseAmountCents('1,2'), 'bad')
  assert.equal(parseAmountCents('12,34,56'), 'bad')
  assert.equal(parseAmountCents('1 2.00'), 'bad')
  assert.equal(parseAmountCents('(-12.00)'), 'bad')
  assert.equal(parseAmountCents('-(12.00)'), 'bad')
  assert.equal(parseAmountCents('12$'), 'bad')
  assert.equal(parseAmountCents('1e5'), 'bad')
  assert.equal(parseAmountCents('Infinity'), 'bad')
  assert.equal(parseAmountCents('NaN'), 'bad')
  assert.equal(parseAmountCents('-Infinity'), 'bad')
  // And the well-formed ones still work, including both negative notations.
  assert.equal(parseAmountCents('(12.00)'), -1200)
  assert.equal(parseAmountCents('-12.00'), -1200)
  assert.equal(parseAmountCents('1,234,567.89'), 123456789)
})

test('a refused file still says which line was wrong', () => {
  // "not enough history" with no detail leaves the person unable to find the
  // row their bank wrote oddly.
  const out = parseBankCsv(
    csv('"01/02/2026","KROGER","-25.00","","Posted"', '"01/03/2026","KROGER","banana","","Posted"'),
  )
  assert.match(out.error ?? '', /not enough history/)
  assert.deepEqual(out.rejected, [{ line: 3, reason: 'bad_amount' }])
})

test('the lower calendar boundary is accepted and everything before it is not', () => {
  assert.equal(parseDateIso('01/01/1970'), '1970-01-01')
  assert.equal(parseDateIso('1970-01-01'), '1970-01-01')
  assert.equal(parseDateIso('00/01/1970'), null)
  assert.equal(parseDateIso('01/00/1970'), null)
})
