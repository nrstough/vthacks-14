// Greps the built bundle, not the source. The bundle is what ships, comments
// are stripped from it, and these are product commitments from CLAUDE.md
// rather than style preferences:
//   - the word "infeasible" never reaches the user;
//   - nothing is ever called "guaranteed";
//   - the offline-fallback chip always discloses itself.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// fileURLToPath, not .pathname: the canonical checkout is "…/Desktop/VT Hacks",
// and a URL's pathname percent-encodes that space into %20, which scandir then
// cannot find. This suite passing depended on running from a path without one.
const DIST = fileURLToPath(new URL('../dist/assets/', import.meta.url))

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

// The boundary is the only thing standing between a render throw and an empty
// page. Tree-shaking or a dropped import in main.tsx would remove it silently,
// and nothing else in the suite renders React, so this grep is the guard.
test('the built bundle still carries the crash fallback', () => {
  const found = bundles().some((code) => code.includes('This page stopped working'))
  assert.ok(found, 'the error boundary fallback text is missing from the bundle')
})

// The sandbox button is how a judge sees the Capital One integration at all.
// It is the one control whose absence would look like a design choice rather
// than a build failure, so it gets the same grep the other two do.
test('the built bundle still offers the sandbox account', () => {
  const found = bundles().some((code) => code.includes('Capital One sandbox'))
  assert.ok(found, 'the sandbox button label is missing from the bundle')
})

// Solana was dropped from the project and the demo wallet deleted with it.
// The risk is not that someone rebuilds the tab; it is that a fragment of it
// survives in the bundle — a fixture, a label, a leftover import — and a judge
// greps the source for a blockchain track we are not entering.
test('the built bundle mentions no blockchain', () => {
  for (const code of bundles()) assert.doesNotMatch(code, /solana/i)
  for (const code of bundles()) assert.doesNotMatch(code, /devnet/i)
})

test('the built bundle carries no demo wallet', () => {
  for (const code of bundles()) assert.doesNotMatch(code, /demo wallet/i)
  for (const code of bundles()) assert.doesNotMatch(code, /wallet-down/)
})

// The two pills are the whole navigation. If either label is missing the app
// still renders, which is exactly why this is worth a grep rather than an eye.
test('the built bundle carries both tab labels', () => {
  // As a quoted string literal, not a bare substring: "Plan" on its own also
  // matches `withPlan`, which the chart uses everywhere. The minifier emits
  // backticks, so all three quote forms count.
  for (const name of ['Plan', 'Ask']) {
    const quoted = [`"${name}"`, `'${name}'`, `\`${name}\``]
    const found = bundles().some((code) => quoted.some((q) => code.includes(q)))
    assert.ok(found, `the ${name} pill label is missing from the bundle`)
  }
})

function stylesheets(): string[] {
  const files = readdirSync(DIST).filter((f) => f.endsWith('.css'))
  assert.ok(files.length > 0, 'no built CSS in dist/assets — run `npm run build` first')
  return files.map((f) => readFileSync(join(DIST, f), 'utf8'))
}

// index.css carries no @tailwind directives, so the Tailwind engine should
// never run over it. If someone adds one, Tailwind's preflight arrives with it
// and resets the box model under a hand-tuned sheet. `--tw-` is the tell.
test('the built CSS carries no Tailwind runtime variables', () => {
  for (const css of stylesheets()) assert.doesNotMatch(css, /--tw-/)
})

// `font-display: swap` is exactly what hides a 404: the fallback renders, the
// page looks fine to whoever built it, and the typeface is simply absent on the
// demo machine. So the fonts are checked as files on disk, not as declarations.
const DIST_ROOT = fileURLToPath(new URL('../dist/', import.meta.url))

test('every font the built CSS asks for is actually in dist/fonts', () => {
  const sheets = stylesheets()
  const referenced = new Set<string>()
  for (const css of sheets) {
    // Quoted and unquoted url() forms both count; the backreference keeps the
    // quote characters matched so `url("x')` cannot slip through.
    for (const m of css.matchAll(/url\((['"]?)\/fonts\/([^'")]+)\1\)/g)) referenced.add(m[2])
  }

  // A vacuous pass is the failure mode this test exists to prevent, so the
  // match count and the families are asserted before the files are. Three,
  // because each family is one variable file covering every weight the page
  // asks for.
  assert.ok(
    referenced.size >= 3,
    `expected at least 3 font references in the built CSS, found ${referenced.size}`,
  )
  for (const family of ['LibreBaskerville', 'Inter', 'JetBrainsMono']) {
    assert.ok(
      [...referenced].some((f) => f.startsWith(family)),
      `no ${family} file is referenced by the built CSS`,
    )
  }

  for (const name of referenced) {
    const path = join(DIST_ROOT, 'fonts', name)
    const size = statSync(path).size
    assert.ok(size > 1024, `dist/fonts/${name} is only ${size} bytes`)
  }
})

// The two faces above the fold are preloaded from index.html, which Vite copies
// through untouched — so a renamed or moved font file leaves the <link> behind
// pointing at a 404. The browser then silently falls back and the page looks
// fine to whoever built it, which is the same failure mode the test above
// exists for, one layer up.
test('every font index.html preloads is actually in dist/fonts', () => {
  const html = readFileSync(join(DIST_ROOT, 'index.html'), 'utf8')
  const hrefs: string[] = []
  for (const tag of html.match(/<link\b[^>]*>/g) ?? []) {
    if (!/rel=["']preload["']/.test(tag)) continue
    if (!/as=["']font["']/.test(tag)) continue
    const href = tag.match(/href=["']([^"']+)["']/)
    assert.ok(href, `a font preload has no href: ${tag}`)
    hrefs.push(href[1])
  }

  // Vacuity guard, as above: a regex that matched nothing would pass silently.
  assert.ok(hrefs.length >= 2, `expected at least 2 font preloads in index.html, found ${hrefs.length}`)

  for (const href of hrefs) {
    assert.ok(href.startsWith('/fonts/'), `preload href ${href} is not under /fonts/`)
    const size = statSync(join(DIST_ROOT, href.slice(1))).size
    assert.ok(size > 1024, `dist${href} is only ${size} bytes`)
  }
})
