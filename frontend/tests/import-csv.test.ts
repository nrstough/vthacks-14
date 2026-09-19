// Parsing a bank export (A1). Money is string arithmetic here, so the tests
// are about exact cents and about what is REPORTED rather than dropped.

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { MAX_ROWS, parseAmountCents, parseBankCsv, parseDateIso, splitCsv } from '../src/lib/importCsv.ts'

const HEADER = '"DATE","DESCRIPTION","AMOUNT","CHECK #","STATUS"'

function csv(...lines: string[]): string {
  return [HEADER, ...lines].join('\n')
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
  const out = parseBankCsv('amount,Status,date,DESCRIPTION\n-25.00,Posted,01/02/2026,KROGER')
  assert.equal(out.error, null)
  assert.deepEqual(out.rows, [{ date: '2026-01-02', description: 'KROGER', amount_cents: -2500 }])
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
    csv('"01/02/2026","KROGER","-25.00","","Posted"', '"01/03/2026","KROGER","-30.00","","Pending"'),
  )
  assert.equal(out.rows.length, 1)
  assert.equal(out.notPosted, 1)
})

test('an unreadable row is reported by line, never silently dropped and never zeroed', () => {
  const out = parseBankCsv(
    csv('"01/02/2026","KROGER","banana","","Posted"', '"02/30/2026","KROGER","-1.00","","Posted"'),
  )
  assert.equal(out.rows.length, 0)
  assert.deepEqual(out.rejected, [
    { line: 2, reason: 'bad_amount' },
    { line: 3, reason: 'bad_date' },
  ])
})

test('a rejection never carries the cell it rejected', () => {
  // The reason codes are a closed set; a message quoting the row would put a
  // private payee into the UI and into anything that logs it.
  const out = parseBankCsv(csv('"01/02/2026","ZZQ7K4 SECRET PAYEE","banana","","Posted"'))
  assert.equal(JSON.stringify(out.rejected).includes('ZZQ7K4'), false)
})

test('a zero-amount row is refused rather than planned around', () => {
  const out = parseBankCsv(csv('"01/02/2026","KROGER","0.00","","Posted"'))
  assert.deepEqual(out.rejected, [{ line: 2, reason: 'zero_amount' }])
})

test('duplicate rows are kept, because two coffees are two coffees', () => {
  const line = '"01/02/2026","STARBUCKS","-4.75","","Posted"'
  const out = parseBankCsv(csv(line, line))
  assert.equal(out.rows.length, 2)
})

test('an empty file and a header-only file each say what is wrong', () => {
  assert.match(parseBankCsv('').error ?? '', /empty/)
  assert.match(parseBankCsv(HEADER).error ?? '', /no transactions/)
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
    csv(
      '"09/16/2026","HARRIS TEETER PAYROLL","1,240.55","","Posted"',
      '"09/15/2026","OAKWOOD PROPERTIES","(1,200.00)","","Posted"',
      '"09/14/2026","DOORDASH*CHIPOTLE","-31.80","","Posted"',
    ),
  )
  assert.equal(out.error, null)
  assert.deepEqual(
    out.rows.map((r) => r.amount_cents),
    [124055, -120000, -3180],
  )
})
