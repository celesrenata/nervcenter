/* fix-verify2.cjs — GL-2 date fix: deadline 2026-11-30T00:00:00Z must render "Nov 30, 2026" */
const { chromium } = require('playwright')
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
;(async () => {
  const b = await chromium.launch({ headless: true })
  const p = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage()
  await p.goto('http://localhost:3001/goals', { waitUntil: 'load' })
  await wait(2500)
  const r = await p.evaluate(() => {
    const cards = [...document.querySelectorAll('[data-testid^="goal-card-"]')]
    return cards.map((c) => c.textContent.replace(/\s+/g, ' ').trim().slice(0, 200))
  })
  console.log('GOAL CARDS:', JSON.stringify(r, null, 1))
  const due = r[0] || ''
  const ok = /Nov 30, 2026/.test(due)
  console.log('DUE-DATE-CORRECT(Nov30):', ok)
  await b.close()
  process.exit(ok ? 0 : 1)
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
