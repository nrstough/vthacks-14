// Pins on the SOURCE stylesheet, where bundle.test.ts pins the built one.
// Two kinds of thing are nailed down here, and nothing else — no colours, no
// sizes, because those are meant to be tuned:
//
//   1. The type system. Which face each token resolves to, and which selectors
//      are on which face. `.num` staying on the text face is the one that
//      matters most: it is carried by the qualifier, the proof paragraph and
//      the reason lines, so pointing it at the mono face would set three
//      paragraphs of prose in monospace.
//   2. The six responsive rules from the handoff, each of which was a real bug
//      once. They are easy to undo by accident and invisible until someone
//      opens the page at a width nobody tested.
//
// Whitespace-tolerant regexes throughout: a formatter must be free to reflow
// this sheet without breaking the suite.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// fileURLToPath, not .pathname: the canonical checkout is "…/Desktop/VT Hacks",
// and a URL's pathname percent-encodes that space into %20, which readFile and
// scandir then cannot find. This suite passing depended on running from a path
// without one.
const CSS = readFileSync(fileURLToPath(new URL('../src/index.css', import.meta.url)), 'utf8')
const CONFIG = readFileSync(fileURLToPath(new URL('../tailwind.config.ts', import.meta.url)), 'utf8')
const FONTS = readdirSync(fileURLToPath(new URL('../public/fonts/', import.meta.url)))

// ---------- the faces that are gone ----------

// Clash Display was the display face, Doto the dot-matrix one, and Array
// arrived with the imported config and was referenced by nothing while being
// 7.0 MB of an 8.0 MB font payload. All three are out; this is the pin that
// keeps a half-finished revert from bringing one back.
test('no Doto, Clash or Array survives in the stylesheet or the config', () => {
  for (const [name, text] of [
    ['index.css', CSS],
    ['tailwind.config.ts', CONFIG],
  ] as const) {
    assert.doesNotMatch(text, /Doto/i, `${name} still mentions Doto`)
    assert.doesNotMatch(text, /Clash/i, `${name} still mentions Clash Display`)
    assert.doesNotMatch(text, /Array/i, `${name} still mentions Array`)
  }
})

test('no Doto, Clash or Array file survives in public/fonts', () => {
  const stale = FONTS.filter((f) => /^(Doto|ClashDisplay|Array)/.test(f))
  assert.deepEqual(stale, [], `stale font files still on disk: ${stale.join(', ')}`)
})

test('public/fonts holds the eight woff2 files the sheet declares', () => {
  const woff2 = FONTS.filter((f) => f.endsWith('.woff2')).sort()
  assert.deepEqual(woff2, [
    'Inter-400.woff2',
    'Inter-500.woff2',
    'Inter-600.woff2',
    'JetBrainsMono-400.woff2',
    'JetBrainsMono-500.woff2',
    'JetBrainsMono-600.woff2',
    'LibreBaskerville-400.woff2',
    'LibreBaskerville-700.woff2',
  ])
})

// ---------- the faces that are here ----------

test('the three font tokens resolve to the three self-hosted families', () => {
  assert.match(CSS, /--display:\s*'Libre Baskerville'/)
  assert.match(CSS, /--mono:\s*'JetBrains Mono'/)
  assert.match(CSS, /--sans:[^;]*'Inter'/)
})

test('headings are on the display face', () => {
  assert.match(CSS, /h1,\s*h2,\s*h3\s*\{[^}]*font-family:\s*var\(--display\)/)
})

// The figures go to the mono face by joining a selector list, not by being
// swept up in `.num` — see the header comment.
test('.rx-amount is on the mono face', () => {
  const rule = CSS.match(/(^|\n)([^{}]*\.rx-amount[^{}]*)\{([^}]*)\}/)
  assert.ok(rule, 'no rule whose selector list contains .rx-amount')
  assert.match(rule[3], /font-family:\s*var\(--mono\)/)
})

test('.num stays on the text face, so prose carrying it is never monospaced', () => {
  const rule = CSS.match(/(^|\n)\.num\s*\{([^}]*)\}/)
  assert.ok(rule, 'no .num rule')
  assert.match(rule[2], /font-family:\s*var\(--sans\)/)
  assert.match(rule[2], /tabular-nums/)
})

// ---------- the responsive rules that were bugs once ----------

// An earlier generation declared `.controls` twice at equal specificity, so the
// later copy won and drew a second panel inside the white .controls-panel card.
// Anchored to the start of a line, because that is exactly the shape of the
// bug: a second UNQUALIFIED, top-level `.controls { … }`. The three other
// occurrences in this sheet are deliberate and are not what broke — two are
// inside media queries (indented) and one is `.controls-panel .controls`, all
// of which differ in specificity or in when they apply.
test('.controls is declared exactly once at the top level', () => {
  const found = CSS.match(/^\.controls\s*\{/gm) ?? []
  assert.equal(found.length, 1, `${found.length} top-level .controls declarations`)
})

// `.main` is a flex column, so without this its children shrink below their own
// content and the hero gets crushed and then clipped.
test('.main children do not flex-shrink', () => {
  assert.match(CSS, /\.main\s*>\s*\*[^{]*\{[^}]*flex:\s*none/)
})

// Every grid track on this page is minmax(0, 1fr) rather than 1fr, because a
// bare 1fr track has an auto minimum and a long unbreakable figure blows the
// column out instead of being contained by it.
test('the grid tracks are all minmax(0, 1fr)', () => {
  const found = (CSS.match(/minmax\(\s*0\s*,\s*1fr\s*\)/g) ?? []).length
  assert.ok(found >= 6, `expected at least 6 minmax(0, 1fr) tracks, found ${found}`)
})

// The 720px rules pin these to column 2. At one column that placement conjures
// an implicit second column and the row silently goes back to two, so the
// placement has to be RELEASED at 640, not just re-aligned.
test('the 640px breakpoint releases the row cells back to column 1', () => {
  assert.match(CSS, /\.rx-amount,\s*\.rx-pain,\s*\.cant\s*\{[^}]*grid-column:\s*1/)
})

// The old reduced-motion block covered the keyframe animations and forgot the
// three transitions the imported sheet had brought with it.
// There is more than one such block — a narrow one beside the `land` keyframes
// and the comprehensive one at the end — so they are checked together. What
// matters is that nothing with motion is left uncovered, not which block covers
// it.
test('reduced motion covers the transitions, not only the animations', () => {
  const blocks = [...CSS.matchAll(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?)\n\}/g)]
  assert.ok(blocks.length > 0, 'no prefers-reduced-motion block')
  const covered = blocks.map((b) => b[1]).join('\n')
  for (const sel of ['.hero', '.panel', '.rx-row']) {
    assert.ok(covered.includes(sel), `reduced motion never mentions ${sel}`)
  }
})

// Adding one would pull Tailwind's preflight in under a hand-tuned sheet. The
// config is kept in step by hand precisely so this stays true.
test('the stylesheet has no @tailwind directives', () => {
  assert.doesNotMatch(CSS, /@tailwind/)
})
