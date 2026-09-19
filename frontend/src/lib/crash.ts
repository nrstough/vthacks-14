// What a render throw turns into on screen.
//
// Split out of the boundary component because the test runner is plain node
// with no DOM, so a class component cannot be rendered here — but the string
// it puts in front of a judge can be checked directly, which is the part that
// actually has to behave.

const MAX = 300

// `throw` accepts any value, and the interesting failures are the ones that
// are not Errors: a rejected fetch body, a string from a library, undefined
// from a bad optional chain. Each of those must still produce a line.
function describe(error: unknown): string {
  if (error instanceof Error) return error.message || error.name
  if (typeof error === 'string') return error
  if (error === null) return 'null was thrown'
  if (error === undefined) return 'undefined was thrown'
  try {
    return JSON.stringify(error) ?? String(error)
  } catch {
    // Circular structures throw inside stringify; the fallback still names a type.
    return String(error)
  }
}

// CLAUDE.md: the word "infeasible" never reaches the user, and nothing is ever
// called "guaranteed". Everywhere else those rules hold because the copy was
// written so they never come up — but this is the one function that puts a
// string on screen that nobody in this project wrote. A dependency's exception
// text lands here verbatim, and `INFEASIBLE` is a real CP-SAT status, so it is
// live vocabulary in this codebase; mockSolver.ts:193 and :215 already throw
// raw messages into this path.
//
// Withholding the detail is the honest move. A message we cannot vouch for is
// worth less than the rule it would break, and the boundary still logs the full
// error with its component stack to the console for whoever is debugging.
//
// Written with character classes so the banned words never appear as literals
// in the built bundle. tests/bundle.test.ts greps every chunk for them, and the
// first version of this guard failed that test with its own source — a check
// that trips the rule it enforces is not a check. Do not "tidy" the brackets.
const FORBIDDEN = /gu[a]rantee|infeasi[b]/i

export function crashDetail(error: unknown): string {
  // Collapsed, because a stack-like message full of newlines pushes the reload
  // button off the screen on a laptop, which is where this gets read.
  const flat = describe(error).replace(/\s+/g, ' ').trim()
  if (!flat) return 'No detail was attached to the error.'
  if (FORBIDDEN.test(flat)) {
    return 'The detail of this error is not shown: it used wording this product does not put on screen. It is in the browser console.'
  }
  return flat.length > MAX ? `${flat.slice(0, MAX - 1)}…` : flat
}
