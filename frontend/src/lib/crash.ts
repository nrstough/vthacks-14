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

export function crashDetail(error: unknown): string {
  // Collapsed, because a stack-like message full of newlines pushes the reload
  // button off the screen on a laptop, which is where this gets read.
  const flat = describe(error).replace(/\s+/g, ' ').trim()
  if (!flat) return 'No detail was attached to the error.'
  return flat.length > MAX ? `${flat.slice(0, MAX - 1)}…` : flat
}
