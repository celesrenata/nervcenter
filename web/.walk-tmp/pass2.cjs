/* pass2 — recapture canonical r2 filenames (fresh state, real data present).
   Overwrites the walk-* PNGs with the FIXED bundle (TAG e59bc39).
   Run: (cd web && node .walk-tmp/pass2.cjs) */
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8080'
const SHOTS = path.resolve(__dirname, '../screenshots/audit-live-r2')
const RUN_START = Date.now()
const E = { shots: [], evidence: {}, contrast: {}, reqFailed: [] }
async function shot(page, name) {
  const p = path.join(SHOTS, name + '.png')
  await page.screenshot({ path: p, type: 'png' })
  E.shots.push({ name, size: fs.statSync(p).size, mtime: fs.statSync(p).mtimeMs })
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function relLum(r, g, b) {
  const f = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
const parsels = (c) => c.replace(/[^0-9,]/g, '').split(',').map(Number)
function ratio(a, b) {
  const l1 = relLum(...parsels(a)), l2 = relLum(...parsels(b))
  return Math.round((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) * 100) / 100
}
const CONTRAST_EVAL = `(() => {
  const out = []
  const seen = new Set()
  for (const el of document.querySelectorAll('main p, main span, main dt, main dd, main h1, main h2, main h3, main h4, main li')) {
    const t = el.childElementCount === 0 ? el.textContent.trim() : ''
    if (!t) continue
    const cs = getComputedStyle(el)
    let bg = null, e = el
    while (e && e instanceof Element) {
      const c = getComputedStyle(e).backgroundColor
      if (c && c !== 'rgba(0, 0, 0, 0)') { bg = c; break }
      e = e.parentElement
    }
    const key = cs.color + '|' + (bg || 'none') + '|' + t.slice(0, 24)
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ text: t.slice(0, 40), sel: el.tagName + '.' + (el.className||'').toString().slice(0,60), fg: cs.color, bg: bg || 'transparent' })
  }
  return out
})()`

;(async () => {
  const browser = await chromium.launch({ headless: true })

  /* ---------------- DESKTOP 1280 ---------------- */
  const dctx = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const pd = await dctx.newPage()
  pd.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) E.reqFailed.push(`${r.status()} ${r.url().replace(BASE, '')}`) })

  // LOGIN + 403 verbatim detail (LG-3) + D-6 contrast of secondary text
  await pd.goto(BASE + '/login', { waitUntil: 'load' }); await wait(900)
  await shot(pd, 'login-desktop')
  await pd.fill('#username', 'local-admin'); await pd.fill('#password', 'x')
  await pd.click('button[type="submit"]'); await wait(1500)
  E.evidence.log403 = await pd.evaluate(() => {
    const live = document.querySelector('[aria-live="assertive"]')
    const err = document.querySelector('#login-credential-error')
    return { live_text: live ? live.textContent.trim() : null, field_error: err ? err.textContent.trim() : null }
  })
  await shot(pd, 'login-403-detail-desktop')
  E.contrast.login = await pd.evaluate(CONTRAST_EVAL)

  // OVERVIEW (real tiles) + D-6 contrast
  await pd.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await wait(1600)
  E.evidence.overview = await pd.evaluate(() => ({
    tiles: document.body.innerText.match(/Active Goals\s*\n?\s*\d+[\s\S]*?Active Incidents\s*\n?\s*\d+/) || null,
    goals_panel: document.body.innerText.includes('R3 walk goal') && document.body.innerText.includes('smoke-goal'),
    agents_panel: document.body.innerText.includes('Planner') && document.body.innerText.includes('audit-r3-probe'),
    pending_tasks_text: (document.body.innerText.match(/Pending Tasks\s*\n?\s*(\d+)/) || [])[1] || null,
    raw_slice: document.body.innerText.replace(/\s+/g, ' ').slice(0, 300),
  }))
  E.contrast.overview = await pd.evaluate(CONTRAST_EVAL)
  await shot(pd, 'overview-desktop')

  // SYSTEMS — badge + in-page WS probe
  await pd.goto(BASE + '/systems', { waitUntil: 'domcontentloaded' })
  await pd.waitForFunction(() => /Connected|Reconnecting/.test(document.body.innerText), { timeout: 8000 }).catch(() => {})
  E.evidence.ws_probe = await pd.evaluate(() => new Promise((resolve) => {
    let r = { opened: false }
    try {
      const ws = new WebSocket('ws://127.0.0.1:8080/api/events/ws')
      ws.onopen = () => { r.opened = true }
      ws.onmessage = (ev) => { try { r.first_frame = JSON.parse(ev.data) } catch (e) {} if (r.opened) { ws.close(); resolve(r) } }
      ws.onerror = () => { r.error = 'socket error'; try { ws.close() } catch (e) {} }
      setTimeout(() => { if (!r.opened) { r.timeout = true } resolve(r) }, 5000)
    } catch (e) { resolve({ error: String(e) }) }
  }))
  E.evidence.systems_badge = await pd.evaluate(() => {
    const b = document.querySelector('[role="status"]')
    return { aria: b ? b.getAttribute('aria-label') : null, text: b ? b.textContent.trim() : null,
      rows: [...document.querySelectorAll('h3')].map((h) => h.textContent.trim()) }
  })
  await shot(pd, 'systems-desktop')

  // AGENTS (desktop)
  await pd.goto(BASE + '/agents', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.evidence.agents_probe_card = await pd.evaluate(() => {
    const t = document.body.innerText
    const i = t.indexOf('audit-r3-probe')
    return { found: i >= 0, near: i >= 0 ? t.slice(i, i + 90).replace(/\s+/g, ' ') : null }
  })
  await shot(pd, 'agents-desktop')

  // TASKS — REAL data (A→B)
  await pd.goto(BASE + '/tasks', { waitUntil: 'domcontentloaded' }); await wait(2000)
  E.evidence.tasks_real = await pd.evaluate(() => ({
    edges: [...document.querySelectorAll('[data-testid^="task-edge-"]')].map((e) => e.getAttribute('data-testid')),
    nodes: [...document.querySelectorAll('[data-testid^="task-node-"]')].map((n) => n.textContent.replace(/\s+/g, ' ').trim().slice(0, 140)),
    svg_elements: document.querySelectorAll('svg').length,
    has_A: document.body.innerText.includes('R3 walk task A'),
    has_B: document.body.innerText.includes('R3 walk task B'),
    legend_or_status: /pending|running|completed|failed/.test(document.body.innerText),
  }))
  await shot(pd, 'tasks-dag-desktop')
  await shot(pd, 'tasks-desktop')
  await shot(pd, 'tasks-dag-edges-desktop')

  // GOALS — create open (desktop) + with real rows
  await pd.goto(BASE + '/goals', { waitUntil: 'domcontentloaded' }); await wait(1500)
  const newBtn = await pd.getByRole('button', { name: /new goal/i }).count()
  if (newBtn) { await pd.getByRole('button', { name: /new goal/i }).click(); await wait(400) }
  E.evidence.goal_form_open = await pd.evaluate(() => !!document.querySelector('#goal-title'))
  await shot(pd, 'goals-create-open-desktop')
  await pd.keyboard.press('Escape')
  const cancel = await pd.locator('button', { hasText: /cancel|close/i }).count()
  if (cancel) { await pd.locator('button', { hasText: /cancel|close/i }).first().click().catch(() => {}); await wait(400) }
  else { await pd.goto(BASE + '/goals', { waitUntil: 'domcontentloaded' }); await wait(1200) }
  E.evidence.goal_card = await pd.evaluate(() => {
    const c = [...document.querySelectorAll('[data-testid^="goal-card-"]')].find((x) => x.textContent.includes('R3 walk goal'))
    return c ? c.textContent.replace(/\s+/g, ' ').trim() : null
  })
  await shot(pd, 'goals-desktop')
  await shot(pd, 'goals-after-create-desktop')
  await pd.close()
  await dctx.close()

  /* ---------------- MOBILE 390 ---------------- */
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 })
  const pm = await mctx.newPage()
  pm.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) E.reqFailed.push(`m:${r.status()} ${r.url().replace(BASE, '')}`) })

  const h = () => pm.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth, hscroll: document.documentElement.scrollWidth > window.innerWidth }))
  E.evidence.m_hscroll = {}

  await pm.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await wait(1600)
  E.evidence.m_hscroll.overview = await h()
  await shot(pm, 'overview-mobile-hamburger-closed')
  const headerBurger = pm.locator('header button[aria-expanded]')
  const dialogClose = pm.locator('div[role="dialog"] button[aria-label="Close navigation"]')
  if ((await headerBurger.count()) > 0) {
    await headerBurger.click(); await wait(500)
    E.evidence.m_hamburger_expanded = await pm.evaluate(() => document.querySelector('[aria-expanded="true"]')?.getAttribute('aria-label') || true)
    await shot(pm, 'overview-mobile-nav-open')
    // Close via the drawer's own button: on the DEPLOYED (unfixed) bundle the
    // drawer (z-30, inset-y-0) paints over the header button (z-20), so the
    // header toggle is unreachable while open (repro finding CC-4b).
    const closeVia = 'drawer-close-button'
    await dialogClose.click(); await wait(400)
    E.evidence.m_hamburger_close = { closeVia, closeOk: await pm.evaluate(() => document.querySelector('[aria-expanded="true"]') === null) }
  }
  await shot(pm, 'overview-mobile')

  await pm.goto(BASE + '/goals', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.evidence.m_hscroll.goals = await h()
  E.evidence.m_goals_r3 = (await pm.getByText('R3 walk goal').count()) > 0
  await shot(pm, 'goals-mobile')
  if (await pm.getByRole('button', { name: /new goal/i }).count()) {
    await pm.getByRole('button', { name: /new goal/i }).click(); await wait(500)
    E.evidence.m_goal_form_open = await pm.evaluate(() => !!document.querySelector('#goal-title'))
    await shot(pm, 'goals-create-mobile')
  }

  await pm.goto(BASE + '/agents', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.evidence.m_hscroll.agents = await h()
  await shot(pm, 'agents-mobile')

  await pm.goto(BASE + '/tasks', { waitUntil: 'domcontentloaded' }); await wait(1800)
  E.evidence.m_hscroll.tasks = await h()
  E.evidence.m_tasks_real = await pm.evaluate(() => ({ has_A: document.body.innerText.includes('R3 walk task A'), edges: document.querySelectorAll('[data-testid^="task-edge-"]').length }))
  await shot(pm, 'tasks-mobile')

  await pm.goto(BASE + '/systems', { waitUntil: 'domcontentloaded' }); await wait(1600)
  E.evidence.m_hscroll.systems = await h()
  E.evidence.m_badge_2 = await pm.evaluate(() => {
    const b = document.querySelector('[role="status"]')
    return b ? b.textContent.trim() : null
  })
  await shot(pm, 'systems-badge-mobile')

  await browser.close()
  fs.writeFileSync(path.join(__dirname, 'pass2.json'), JSON.stringify(E, null, 2))
  console.log('PASS2 WROTE pass2.json')
  console.log(JSON.stringify({ shots: E.shots.map((s) => s.name), evidence: E.evidence, reqFailed: E.reqFailed }, null, 1).slice(0, 7000))
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
