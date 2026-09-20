// Pins on the SOURCE stylesheet, where bundle.test.ts pins the built one.
// Three kinds of thing are nailed down here, and nothing else — no colour
// VALUES, no sizes, because those are meant to be tuned:
//
//   1. The type system. Which face each token resolves to, and which selectors
//      are on which face. `.num` staying on the text face is the one that
//      matters most: it is carried by the qualifier, the proof paragraph and
//      the reason lines, so pointing it at the mono face would set three
//      paragraphs of prose in monospace.
//   2. The six responsive rules from the handoff, each of which was a real bug
//      once. They are easy to undo by accident and invisible until someone
//      opens the page at a width nobody tested.
//   3. That white is a token rather than a literal. Not which white — that a
//      rule outside `:root` never carries its own, so the shell retunes in one
//      place.
//
// Whitespace-tolerant regexes throughout: a formatter must be free to reflow
// this sheet without breaking the suite.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
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
// A3 names four places: the stylesheet, the config, every source file, and the
// built CSS. The built CSS is what ships; `src/` is where a stray import or a
// hard-coded font-family in a component would hide from the stylesheet pin.
function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const full = join(dir, f)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}
const SRC_DIR = fileURLToPath(new URL('../src/', import.meta.url))
const DIST_ASSETS = fileURLToPath(new URL('../dist/assets/', import.meta.url))
const SRC_FILES: [string, string][] = walk(SRC_DIR)
  .filter((f) => /\.(tsx?|css|html)$/.test(f))
  .map((f) => [f.slice(SRC_DIR.length), readFileSync(f, 'utf8')])
const BUILT_CSS: [string, string][] = readdirSync(DIST_ASSETS)
  .filter((f) => f.endsWith('.css'))
  .map((f) => [`dist/assets/${f}`, readFileSync(join(DIST_ASSETS, f), 'utf8')])

test('no Doto, Clash or Array survives in the stylesheet, the config, src/, or the built CSS', () => {
  assert.ok(SRC_FILES.length > 10, 'src/ walk found nothing')
  assert.ok(BUILT_CSS.length > 0, 'no built CSS in dist/assets — run `npm run build` first')
  for (const [name, text] of [
    ['index.css', CSS],
    ['tailwind.config.ts', CONFIG],
    ...SRC_FILES,
    ...BUILT_CSS,
  ] as const) {
    assert.doesNotMatch(text, /Doto/i, `${name} still mentions Doto`)
    // The font's name, not the English word: reasons.ts has a "clash" reason.
    assert.doesNotMatch(text, /Clash ?Display/i, `${name} still mentions Clash Display`)
    // The font, not the JavaScript type: `Array.isArray` and `Array<T>` are
    // fine, a quoted family name or a font file is not.
    assert.doesNotMatch(text, /['"]Array['"]|Array-(Regular|Bold|Semibold|Wide)|font-family:[^;]*\bArray\b/, `${name} still mentions the Array font`)
  }
})

test('no Doto, Clash or Array file survives in public/fonts', () => {
  const stale = FONTS.filter((f) => /^(Doto|ClashDisplay|Array)/.test(f))
  assert.deepEqual(stale, [], `stale font files still on disk: ${stale.join(', ')}`)
})

// One variable file per family, not one per weight: Google serves a single
// file and hands back the same URL for every weight, so a per-weight layout
// ships the same three payloads several times over.
test('public/fonts holds the three variable files the sheet declares', () => {
  const woff2 = FONTS.filter((f) => f.endsWith('.woff2')).sort()
  assert.deepEqual(woff2, [
    'Inter-Variable.woff2',
    'JetBrainsMono-Variable.woff2',
    'LibreBaskerville-Variable.woff2',
  ])
})

// A range, not a single value. With one value the browser treats the file as
// covering that weight alone and synthesises the rest — and synthesis is off
// on the headings, so a bold wordmark would silently render regular.
test('each family declares the weight range its file actually carries', () => {
  for (const [family, range] of [
    ['Libre Baskerville', '400 700'],
    ['Inter', '100 900'],
    ['JetBrains Mono', '400 800'],
  ] as const) {
    const face = CSS.match(new RegExp(`@font-face\\s*\\{[^}]*font-family:\\s*'${family}'[^}]*\\}`))
    assert.ok(face, `no @font-face for ${family}`)
    assert.match(face[0], new RegExp(`font-weight:\\s*${range}\\s*;`))
    assert.match(face[0], /url\('\/fonts\/[A-Za-z]+-Variable\.woff2'\)/)
  }
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

// RETIRED, and replaced by its inverse.
//
// The sixth responsive pin used to assert that `.wallet, .wallet-down,
// .wallet-loading` shared a `background: var(--bg)` card rule. The wallet was
// the one view with no card of its own, and on the gradient it was dark text
// on deep blue — handoff bug 5. The Solana demo wallet has been deleted, so
// the rule it guarded is gone and the pin would only fail. What is worth
// guarding now is the opposite: that none of it grew back.
test('no wallet rule survives in the stylesheet', () => {
  const bare = CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(bare, /\.wallet/, 'a .wallet selector is back in the stylesheet')
})

// The explainer's root is a `.panel`, and `.panel { display: flex }` is an
// author declaration that beats the user agent's `[hidden] { display: none }`
// at any specificity. Without this rule the hidden tab renders in full under
// the plan list — measured at 363px tall, with six focusable descendants still
// in the tab order. It is the kind of failure that looks like nothing was
// wired up at all, so it is pinned.
test('a hidden child of .main is actually hidden', () => {
  const bare = CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  const rule = [...bare.matchAll(/(?:^|\n)([^{}@]+)\{([^{}]*)\}/g)].find(
    (r) => /\.main\s*>\s*\[hidden\]/.test(r[1]) && /display:\s*none/.test(r[2]),
  )
  assert.ok(rule, 'nothing declares display: none for a hidden child of .main')
})

// Scoped, not global-and-important. If this ever needs `!important` the rule
// is in the wrong place; the sheet has managed without one so far.
test('the stylesheet carries no !important', () => {
  // Comments are stripped first: the rule above explains in prose why it is
  // not `!important`, and matching the raw file would fail on that sentence.
  const bare = CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(bare, /!\s*important/)
})

// ---------- the tokens that replaced the literal whites ----------

// Every white on this page is a token, so the shell retunes as one and no rule
// is left behind on the old value. The two `:root` blocks are the one place a
// literal is allowed to live, and are stripped before the check; whatever is
// left is a rule that kept its own.
test('no rule outside the :root blocks carries a literal white', () => {
  const stripped = CSS.replace(/:root\s*\{[\s\S]*?\n\}/g, '')
  assert.doesNotMatch(stripped, /#fff\b/i, 'a rule outside :root still uses #fff')
  assert.doesNotMatch(stripped, /#ffffff\b/i, 'a rule outside :root still uses #ffffff')
  assert.doesNotMatch(
    stripped,
    /rgba\(\s*255\s*,\s*255\s*,\s*255/,
    'a rule outside :root still uses a literal rgba white',
  )
})
