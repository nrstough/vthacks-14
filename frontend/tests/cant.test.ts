import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { controlFor } from '../src/lib/cant.ts'
import { domId } from '../src/lib/focus.ts'
import { NONE, fromIds, toggle } from '../src/lib/overrides.ts'

const GYM = 'c_gym'

test('a plan row asks whether the user cannot do the change, unticked', () => {
  const c = controlFor('plan', NONE, GYM, 'Gym')
  assert.equal(c.checked, false)
  assert.equal(c.text, 'Can’t do this')
  assert.equal(c.ariaLabel, 'Can’t do this: Gym')
})

test('a plan row the user ruled out is ticked', () => {
  assert.equal(controlFor('plan', fromIds([GYM]), GYM, 'Gym').checked, true)
})

test('a left-out row asks whether the user can do it, and starts ticked', () => {
  // The counterfactual for removing the inversion: a change the solver left out
  // is still something the user CAN do, so the box is ticked.
  const c = controlFor('out', NONE, GYM, 'Gym')
  assert.equal(c.checked, true)
  assert.equal(c.text, 'Can do this')
  assert.equal(c.ariaLabel, 'Can do this: Gym')
})

test('a left-out row the user ruled out is unticked', () => {
  assert.equal(controlFor('out', fromIds([GYM]), GYM, 'Gym').checked, false)
})

test('the id is the one focus.ts prefix-tests, in both sections', () => {
  assert.equal(controlFor('plan', NONE, GYM, 'Gym').id, domId(GYM))
  assert.equal(controlFor('out', NONE, GYM, 'Gym').id, domId(GYM))
})

test('toggling the override flips the tick in both sections', () => {
  const after = toggle(NONE, GYM)
  assert.notEqual(controlFor('plan', after, GYM, 'Gym').checked, controlFor('plan', NONE, GYM, 'Gym').checked)
  assert.notEqual(controlFor('out', after, GYM, 'Gym').checked, controlFor('out', NONE, GYM, 'Gym').checked)
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
