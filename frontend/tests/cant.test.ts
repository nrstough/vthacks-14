import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { CANT_DO_THIS, controlFor } from '../src/lib/cant.ts'
import { domId } from '../src/lib/focus.ts'
import { NONE, fromIds, toggle } from '../src/lib/overrides.ts'

const GYM = 'c_gym'

test('a row asks whether the user cannot do the change, and starts unticked', () => {
  const c = controlFor(NONE, GYM, 'Gym')
  assert.equal(c.checked, false)
  assert.equal(c.text, 'Can’t do this')
  assert.equal(c.ariaLabel, 'Can’t do this: Gym')
})

test('a row the user ruled out is ticked', () => {
  assert.equal(controlFor(fromIds([GYM]), GYM, 'Gym').checked, true)
})

test('the reading does not depend on which section the row is in', () => {
  // This is the whole point of the change. The left-out list used to ask the
  // opposite question and start ticked, which put eight checkmarks under a
  // heading saying those changes had been left out. Same set, same id, same
  // answer: one call, one result.
  const available = controlFor(NONE, GYM, 'Gym')
  const ruledOut = controlFor(fromIds([GYM]), GYM, 'Gym')
  assert.equal(available.text, ruledOut.text)
  assert.equal(available.checked, false)
  assert.equal(ruledOut.checked, true)
})

test('an untouched row is never ticked, whatever else is ruled out', () => {
  // The counterfactual for reintroducing an inversion: if any section started
  // ticked, this would fail for the row that section renders.
  const others = fromIds(['c_card_min', 'c_spotify'])
  assert.equal(controlFor(others, GYM, 'Gym').checked, false)
})

test('the id is the one focus.ts prefix-tests', () => {
  assert.equal(controlFor(NONE, GYM, 'Gym').id, domId(GYM))
})

test('toggling the override flips the tick', () => {
  const after = toggle(NONE, GYM)
  assert.notEqual(controlFor(after, GYM, 'Gym').checked, controlFor(NONE, GYM, 'Gym').checked)
})

test('the label is exported once, so the two call sites cannot drift', () => {
  assert.equal(controlFor(NONE, GYM, 'Gym').text, CANT_DO_THIS)
  assert.ok(controlFor(NONE, GYM, 'Gym').ariaLabel.startsWith(CANT_DO_THIS))
})

test('the dom id lives in one place, and the component still wires onFocus', () => {
  // `focus.ts` prefix-tests `cant-`, so a second place building that id is a
  // silent way to break focus restore. It is built once, by `domId`.
  const src = fileURLToPath(new URL('../src/', import.meta.url))

  function walk(dir: string): string[] {
    const out: string[] = []
    for (const name of readdirSync(dir)) {
      const full = join(dir, name)
      if (statSync(full).isDirectory()) out.push(...walk(full))
      else if (/\.tsx?$/.test(name)) out.push(full)
    }
    return out
  }

  const files = walk(src)
  assert.ok(files.length > 0, 'no source files were read')

  const components = files.filter((f) => f.includes(`${join('src', 'components')}`))
  assert.ok(components.length > 0, 'no component files were read')
  for (const f of components) {
    assert.equal(
      (readFileSync(f, 'utf8').match(/cant-/g) ?? []).length,
      0,
      `${f} builds the checkbox id itself`,
    )
  }

  const templates = files.filter((f) => readFileSync(f, 'utf8').includes('`cant-'))
  assert.deepEqual(
    templates.map((f) => f.slice(src.length)),
    [join('lib', 'focus.ts')],
  )

  const list = readFileSync(join(src, 'components', 'PrescriptionList.tsx'), 'utf8')
  assert.match(list, /onFocus=\{/)
})

test('each section hands controlFor its own row, not the other section\'s', () => {
  // The sections no longer differ in how they read the set, so swapping the
  // calls would no longer flip any checkbox — but it would still put the plan
  // row's label on a left-out row and break the accessible name. Tie each
  // call to the row data only that section has.
  const src = fileURLToPath(new URL('../src/components/PrescriptionList.tsx', import.meta.url))
  const code = readFileSync(src, 'utf8')
  assert.equal(code.split('controlFor(ruledOut, p.candidate_id, p.label)').length - 1, 1)
  assert.equal(code.split('controlFor(ruledOut, c.id, c.label)').length - 1, 1)
  assert.equal(code.split('controlFor(').length - 1, 2)
})
