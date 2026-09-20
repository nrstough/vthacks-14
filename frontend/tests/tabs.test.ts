import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  DEFAULT_TAB,
  TABS,
  isPlanVisible,
  label,
  showsAlarmDot,
} from '../src/lib/tabs.ts'

test('there are two tabs, plan and ask', () => {
  assert.deepEqual([...TABS], ['plan', 'ask'])
})

test('the app opens on the plan tab', () => {
  // The four-minute demo runs entirely here. Opening anywhere else costs a
  // click before the first word.
  assert.equal(DEFAULT_TAB, 'plan')
})

test('the pills are called Plan and Ask', () => {
  assert.equal(label('plan'), 'Plan')
  assert.equal(label('ask'), 'Ask')
})

test('the plan list is on screen only on the plan tab', () => {
  assert.equal(isPlanVisible('plan'), true)
  assert.equal(isPlanVisible('ask'), false)
})

test('the alarm dot is spent only on tier 3', () => {
  assert.equal(showsAlarmDot('plan', 3), true)
  assert.equal(showsAlarmDot('plan', 1), false)
  assert.equal(showsAlarmDot('plan', 2), false)
})

test('the alarm dot belongs to the plan pill, never the ask pill', () => {
  // It is a pointer at the tab whose verdict is off screen. On the ask pill it
  // would be pointing at itself.
  assert.equal(showsAlarmDot('ask', 3), false)
})

test('every tab has a label, so no pill can render empty', () => {
  for (const t of TABS) assert.ok(label(t).length > 0, `${t} has no label`)
})

test('the default tab is one of the tabs', () => {
  assert.ok(TABS.includes(DEFAULT_TAB))
})

// ---------- the helpers are wired into rendering, not merely exported ----------
//
// Everything above proves the rules. None of it proves TopNav obeys them: the
// pills could be hard-coded strings with the module sitting unused beside
// them and every test would still pass. There is no DOM runner here, so the
// call sites are pinned at the source — the same technique `cant.test.ts`
// uses for the checkbox.

const read = (p: string) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), 'utf8')

test('TopNav builds its pills from the module, not from literals', () => {
  const nav = read('../src/components/TopNav.tsx')
  assert.match(nav, /TABS\.map\(/, 'the pills are not generated from TABS')
  assert.match(nav, /label\(t\)/, 'the pill text does not come from label()')
  assert.match(nav, /showsAlarmDot\(t, res\.tier\)/, 'the dot is not placed by showsAlarmDot')
  // The literals would be the giveaway that someone bypassed the module.
  assert.doesNotMatch(nav, /["'`]Checking account["'`]/, 'the old pill label is back')
  assert.doesNotMatch(nav, /["'`]Demo wallet["'`]/, 'the wallet pill is back')
})

test('the disclosure chip is outside the pill nav, so no tab can drop it', () => {
  // CLAUDE.md makes the chip binding. `bundle.test.ts` proves the string
  // ships; this proves it is not inside anything a tab switch can unmount.
  const nav = read('../src/components/TopNav.tsx')
  const chip = nav.indexOf('Running on the built-in solver')
  const navEnd = nav.indexOf('</nav>')
  assert.ok(chip > 0, 'the chip text is not in TopNav')
  assert.ok(navEnd > 0 && chip > navEnd, 'the chip moved inside the pill nav')
})

test('App opens on the default tab with the left-out list collapsed', () => {
  // Two seeds that no pure test can reach, and both are acceptance criteria:
  // "Plan is the default" and "the list starts collapsed".
  const app = read('../src/App.tsx')
  assert.match(app, /useState<Tab>\(DEFAULT_TAB\)/, 'the default tab is not DEFAULT_TAB')
  assert.match(app, /const \[consideredOpen, setConsideredOpen\] = useState\(false\)/,
    'the left-out list does not start collapsed')
})

test('App asks the module whether the plan is visible', () => {
  const app = read('../src/App.tsx')
  assert.match(app, /isPlanVisible\(tab\)/, 'planVisible is derived by hand, not by the rule')
  assert.match(app, /decideConsidered\(/, 'the open/close rule is not the one under test')
})
