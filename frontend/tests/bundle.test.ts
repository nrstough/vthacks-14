// Greps the built bundle, not the source. The bundle is what ships, comments
// are stripped from it, and these are product commitments from CLAUDE.md
// rather than style preferences:
//   - the word "infeasible" never reaches the user;
//   - nothing is ever called "guaranteed";
//   - the offline-fallback chip always discloses itself.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const DIST = new URL('../dist/assets/', import.meta.url).pathname

function bundles(): string[] {
  // Deliberately not skipped when dist/ is missing: a check that silently
  // passes because it had nothing to read is worse than no check.
  const files = readdirSync(DIST).filter((f) => f.endsWith('.js'))
  assert.ok(files.length > 0, 'no built JS in dist/assets — run `npm run build` first')
  return files.map((f) => readFileSync(join(DIST, f), 'utf8'))
}

test('the built bundle never promises a guarantee', () => {
  for (const code of bundles()) assert.doesNotMatch(code, /guarantee/i)
})

test('the built bundle never contains the word infeasible', () => {
  for (const code of bundles()) assert.doesNotMatch(code, /infeasib/i)
})

test('the built bundle still discloses the offline fallback', () => {
  const found = bundles().some((code) => code.includes('Running on the built-in solver'))
  assert.ok(found, 'the fallback chip text is missing from the bundle')
})
