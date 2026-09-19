// Parse a bank CSV in the browser. Nothing here talks to the network: the
// file is read, turned into rows, and the rows are what get posted.
//
// Money is parsed by STRING ARITHMETIC, never by parseFloat. `19.99 * 100` is
// 1998.9999999999998 in binary floating point, and `Math.round` hides that
// until the one input where it does not. This project's rule is that no float
// ever touches money, and a CSV parser is exactly where that rule gets broken.

import type { ImportRow } from '../types'

export const MAX_ROWS = 20000
// Below this there is no rhythm to find and no spending to summarise, so the
// honest answer is "not enough history" rather than a confident empty plan.
export const MIN_ROWS = 10

export type RejectCode =
  | 'no_date'
  | 'bad_date'
  | 'no_amount'
  | 'bad_amount'
  | 'too_many_decimals'
  | 'zero_amount'
  | 'no_description'
  | 'not_posted'

export interface ParseResult {
  rows: ImportRow[]
  // Line number and code only. Never the cell: a rejection message is one of
  // the places a private statement leaks back out.
  rejected: { line: number; reason: RejectCode }[]
  notPosted: number
  totalLines: number
  error: string | null
}

// RFC 4180: quoted fields may contain commas, newlines and doubled quotes.
export function splitCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  let i = 0
  while (i < text.length) {
    const c = text[i]
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i += 2
          continue
        }
        quoted = false
        i += 1
        continue
      }
      field += c
      i += 1
      continue
    }
    if (c === '"') {
      quoted = true
      i += 1
      continue
    }
    if (c === ',') {
      row.push(field)
      field = ''
      i += 1
      continue
    }
    if (c === '\r') {
      i += 1
      continue
    }
    if (c === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
      i += 1
      continue
    }
    field += c
    i += 1
  }
  if (field !== '' || row.length > 0) {
    row.push(field)
    rows.push(row)
  }
  return rows
}

/**
 * Cents from a string, exactly, or a reason it could not be read.
 *
 * The grammar is validated BEFORE anything is stripped. Stripping first and
 * parsing what is left turns malformed money into usable money: `1,2` became
 * twelve dollars, `1 2.00` became twelve, and `(-12.00)` — a minus sign
 * inside accounting parentheses, which is two negatives — became a POSITIVE
 * twelve dollars. An outflow silently entering the plan as an inflow is the
 * worst failure this parser has, because every number downstream is then
 * confidently wrong in the safe-looking direction.
 */
export function parseAmountCents(raw: string): number | 'bad' | 'decimals' {
  let text = raw.trim()
  if (text === '') return 'bad'

  let negative = false
  if (text.startsWith('(') && text.endsWith(')')) {
    negative = true
    text = text.slice(1, -1).trim()
    // Parentheses ALREADY mean negative; a sign as well is malformed, not
    // a double negative and not a positive.
    if (/^[-+]/.test(text)) return 'bad'
  } else if (text.startsWith('-') || text.startsWith('+')) {
    negative = text.startsWith('-')
    text = text.slice(1).trim()
  } else if (text.includes('(') || text.includes(')')) {
    return 'bad'
  }

  if (text.startsWith('$')) text = text.slice(1).trim()
  if (text.includes('$')) return 'bad'

  // Reported apart from `bad` so the row can say WHY: a third decimal is a
  // different mistake from a letter.
  const dot = text.indexOf('.')
  if (dot >= 0 && /^[\d,]*\.\d+$/.test(text) && text.length - dot - 1 > 2) return 'decimals'

  // Either grouped in threes, or not grouped at all. `1,2` is neither.
  if (!/^(?:\d{1,3}(?:,\d{3})+|\d*)(?:\.\d{1,2})?$/.test(text)) return 'bad'

  const [whole = '', fraction = ''] = text.split('.')
  const digits = whole.replace(/,/g, '')
  if (digits === '' && fraction === '') return 'bad'
  const cents = Number(digits || '0') * 100 + Number(fraction.padEnd(2, '0') || '0')
  if (!Number.isSafeInteger(cents)) return 'bad'
  return negative ? -cents : cents
}

/**
 * A date from the three shapes banks export, validated by COMPONENT.
 *
 * `new Date('2026-02-30')` does not fail, it rolls into March. Rebuilding the
 * date and comparing the parts back is what turns that into a rejection.
 */
export function parseDateIso(raw: string): string | null {
  const text = raw.trim()
  let y: number, m: number, d: number
  let match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text)
  if (match) {
    ;[, y, m, d] = match.map(Number) as unknown as [never, number, number, number]
  } else {
    match = /^(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})$/.exec(text)
    if (!match) return null
    m = Number(match[1])
    d = Number(match[2])
    const year = Number(match[3])
    // Two-digit years: 70 and above are the twentieth century. A statement
    // from '99 is 1999; one from '26 is 2026.
    y = match[3].length === 2 ? (year >= 70 ? 1900 + year : 2000 + year) : year
  }
  if (m < 1 || m > 12 || d < 1 || d > 31) return null
  const made = new Date(Date.UTC(y, m - 1, d))
  if (made.getUTCFullYear() !== y || made.getUTCMonth() !== m - 1 || made.getUTCDate() !== d) return null
  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const WANTED = ['date', 'description', 'amount', 'status'] as const

export function parseBankCsv(text: string): ParseResult {
  const empty: ParseResult = { rows: [], rejected: [], notPosted: 0, totalLines: 0, error: null }
  const table = splitCsv(text).filter((r) => r.some((c) => c.trim() !== ''))
  if (table.length === 0) return { ...empty, error: 'That file is empty.' }

  const header = table[0].map((h) => h.trim().toLowerCase().replace(/[^a-z]/g, ''))
  const at: Record<string, number> = {}
  for (const want of WANTED) {
    const index = header.indexOf(want)
    if (index >= 0) at[want] = index
  }
  if (at.date === undefined || at.description === undefined || at.amount === undefined) {
    return { ...empty, error: 'That file needs Date, Description and Amount columns.' }
  }

  const lines = table.slice(1)
  if (lines.length === 0) return { ...empty, error: 'That file has a header and no transactions.' }
  if (lines.length > MAX_ROWS) {
    return { ...empty, error: `That file has ${lines.length} rows; the limit is ${MAX_ROWS}.` }
  }

  const rows: ImportRow[] = []
  const rejected: ParseResult['rejected'] = []
  let notPosted = 0

  lines.forEach((cells, i) => {
    const line = i + 2
    if (at.status !== undefined) {
      // A blank cell in a file that HAS a status column is not a posted
      // transaction. Treating it as one plans around money that may never
      // leave, which is the wrong direction to guess in.
      const status = (cells[at.status] ?? '').trim().toLowerCase()
      if (status !== 'posted') {
        notPosted += 1
        return
      }
    }
    const description = (cells[at.description] ?? '').trim()
    if (description === '') {
      rejected.push({ line, reason: 'no_description' })
      return
    }
    const rawDate = (cells[at.date] ?? '').trim()
    if (rawDate === '') {
      rejected.push({ line, reason: 'no_date' })
      return
    }
    const date = parseDateIso(rawDate)
    if (date === null) {
      rejected.push({ line, reason: 'bad_date' })
      return
    }
    const rawAmount = (cells[at.amount] ?? '').trim()
    if (rawAmount === '') {
      rejected.push({ line, reason: 'no_amount' })
      return
    }
    const cents = parseAmountCents(rawAmount)
    if (cents === 'decimals') {
      rejected.push({ line, reason: 'too_many_decimals' })
      return
    }
    if (cents === 'bad') {
      rejected.push({ line, reason: 'bad_amount' })
      return
    }
    if (cents === 0) {
      rejected.push({ line, reason: 'zero_amount' })
      return
    }
    // Duplicates are kept on purpose: two coffees on one day are two coffees.
    rows.push({ date, description: description.slice(0, 200), amount_cents: cents })
  })

  if (rows.length < MIN_ROWS) {
    // `rejected` and `notPosted` survive the refusal: a file with one good
    // row and one bad amount must still say WHICH line was bad, or the
    // person is told "not enough history" with no way to find the problem.
    return {
      ...empty,
      rejected,
      notPosted,
      totalLines: lines.length,
      error: `That file has ${rows.length} usable ${rows.length === 1 ? 'transaction' : 'transactions'}; not enough history to plan from.`,
    }
  }

  return { rows, rejected, notPosted, totalLines: lines.length, error: null }
}
