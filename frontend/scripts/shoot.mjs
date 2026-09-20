// Headless-Chrome screenshots over CDP. Usage: node shoot.mjs <base-url> <out-prefix>
// Captures: plan default, tier 3 ($60.00), ask — at 1440x900 and 390x844.
// Lives in the repo so the next lane does not have to rediscover the recipe;
// the handoff docs say how to run it.
import { writeFileSync } from 'node:fs'
const [,, base = 'http://localhost:5175', prefix = 'shot'] = process.argv
const list = await (await fetch('http://127.0.0.1:9222/json')).json()
const page = list.find(t => t.type === 'page') ?? (await (await fetch('http://127.0.0.1:9222/json/new?about:blank', {method:'PUT'})).json())
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise(r => ws.onopen = r)
let id = 0; const pending = new Map()
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) } }
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const sleep = ms => new Promise(r => setTimeout(r, ms))
const evalJs = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value
// Throws rather than returning 'missing'. It used to log and carry on, which
// meant a renamed or unmounted control produced a screenshot of whatever was
// already on screen — and that file then got committed under docs/shots/ as
// evidence of a view that was never rendered.
// `scope` matters: "Ask" is both a pill and the explainer's submit button, so
// an unscoped search picks whichever comes first in the DOM and would quietly
// shoot the wrong view. Throws rather than returning 'missing', which is how a
// screenshot of a view that was never rendered used to get committed as
// evidence.
const clickText = async (t, scope = 'button') => {
  const r = await evalJs(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(scope)})].find(x => x.textContent.trim() === ${JSON.stringify(t)}); if (!b) return 'missing'; b.click(); return 'ok' })()`)
  if (r !== 'ok') throw new Error(`no ${scope} reads exactly ${JSON.stringify(t)} — nothing was captured for it`)
  return r
}
const clickPill = t => clickText(t, '.pillnav button')
const shot = async name => { await sleep(700); const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true }); writeFileSync(`${prefix}-${name}.png`, Buffer.from(r.result.data, 'base64')); console.log('wrote', `${prefix}-${name}.png`) }
await send('Page.enable'); await send('Runtime.enable')
for (const [w, h, tag] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: tag === 'mobile' })
  await send('Page.navigate', { url: base }); await sleep(1800)
  await shot(`${tag}-plan`)
  console.log('tier3 click:', await clickText('$60.00')); await sleep(900); await shot(`${tag}-tier3`)
  console.log('ask click:', await clickPill('Ask')); await sleep(900); await shot(`${tag}-ask`)
  console.log('back to plan:', await clickPill('Plan')); await sleep(600)
}
ws.close(); process.exit(0)
