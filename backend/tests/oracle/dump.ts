// Runs the frontend's reference solver as a subprocess so the Python service can
// be compared against it.
//
// The point of checking against this file rather than a Python port of it is that
// a port carries its author's misreadings across with it. This is the code the
// browser actually runs, executed by a different language runtime, reached only
// through JSON.
//
// Reads a JSON array of requests on stdin, writes a JSON array of results.
// Batched deliberately: Node costs ~100ms to start, and a per-request process
// would dominate the test suite's runtime.

import { solve } from '../../../frontend/src/solver/mockSolver.ts'

let raw = ''
process.stdin.setEncoding('utf8')
for await (const chunk of process.stdin) raw += chunk

const requests = JSON.parse(raw) as Array<Record<string, unknown>>
const out = requests.map((r) => {
  const { previous_plan = [], ...request } = r
  try {
    return { ok: true, response: solve(request as never, previous_plan as string[]) }
  } catch (e) {
    // Surfaced rather than thrown so one bad instance identifies itself instead
    // of failing the whole batch anonymously.
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
})

process.stdout.write(JSON.stringify(out))
