/* FINAL recapture walk against deployed TAG e59bc39 (port-forward :8080).
   Desktop 1280x720 + Mobile 390x844. Outputs:
   - screenshots OVERWRITE web/screenshots/audit-live-r2/*.png
   - evidence JSON → web/.walk-tmp/walk-r3-final.json
   Run: (cd web && node .walk-tmp/walk.cjs) */
const http = require('http')
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:8080'
const SHOTS = path.resolve(__dirname, '../screenshots/audit-live-r2')
const E = { perView: {}, shots: [], checks: {}, api: {}, contrast: null, consoleErrors: {}, reqFailed: {} }
function shot(name) { const p = path.join(SHOTS, name); fs.writeFileSync(p, null); return p }
async function s(page, name) { const p = path.join(SHOTS, name + '.png'); await page.screenshot({ path: p, type: 'png' });
  const sz = fs.statSync(p).size; E.shots.push({ name, size: sz, blank: sz < 8000 }) }
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

async function api(method, url, body) {
  return new Promise((res, rej) => {
    const data = body ? JSON.stringify(body) : null
    const rq = http.request(BASE + url, { method, headers: { 'content-type': 'application/json' } }, (rs) => {
      let s = ''; rs.on('data', (c) => (s += c)); rs.on('end', () => res({ status: rs.statusCode, body: s.slice(0, 900) }))
    })
    rq.on('error', rej); rq.end(data)
  })
}

function attach(page, view) {
  E.consoleErrors[view] = []; E.reqFailed[view] = []
  page.on('console', (m) => m.type() === 'error' && E.consoleErrors[view].push(m.text().slice(0, 240)))
  page.on('requestfailed', (rq) => E.reqFailed[view].push(`${rq.method()} ${rq.url().slice(0, 180)} :: ${rq.failure()?.errorText || 'no response'}`))
  page.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) E.reqFailed[view].push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, '').slice(0, 120)}`) })
}

async function main() {
  const browser = await chromium.launch({ headless: true })

  /* ================= DESKTOP 1280 ================= */
  const dctx = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const pd = await dctx.newPage()

  // ---------- LOGIN ----------
  attach(pd, 'login'); await pd.goto(BASE + '/login', { waitUntil: 'load' }); await wait(900)
  E.checks.LG1_scan = { desktop_text: /default credential/i.test(await pd.evaluate(() => document.body.innerText)) }
  E.checks.LG4_ssoButton = await pd.evaluate(() => {
    const btns = [...document.querySelectorAll('button,a')].map((b) => b.textContent.trim())
    return { sso_visible: btns.some((t) => /sso|google|okta/i.test(t)), buttons: btns }
  })
  E.checks.D23_labels = await pd.evaluate(() => {
    const u = document.querySelector('#username'), p = document.querySelector('#password')
    const lbl = (id) => { const l = document.querySelector(`label[for="${id}"]`); return l ? l.textContent.trim() : null }
    return { username_for: lbl('username'), password_for: lbl('password'),
      title_tag: document.querySelector('title')?.textContent, has_h1: !!document.querySelector('h1') }
  })
  await s(pd, 'login-desktop')

  // LG-3: 401 field association
  await pd.fill('#username', 'admin')
  await pd.fill('#password', 'not-a-secret')
  const r401 = []
  pd.on('response', (re) => { if (re.url().endsWith('/api/auth/login')) r401.push(re.status()) })
  await pd.click('button[type="submit"]'); await wait(1500)
  E.checks.LG3_401 = await pd.evaluate(() => {
    const err = document.querySelector('#login-credential-error')
    const u = document.querySelector('#username'), p = document.querySelector('#password')
    const a = (el) => el ? { descd: el.getAttribute('aria-describedby'), invalid: el.getAttribute('aria-invalid') } : null
    return { http: null, alert: err ? err.textContent.trim() : null, u: a(u), p: a(p) }
  })
  E.checks.LG3_401.http = r401[0] ?? null
  await s(pd, 'login-error-desktop')

  // LG-3: 403 verbatim
  await pd.evaluate(() => { ['username', 'password'].forEach((id) => document.getElementById(id).value = '') })
  await pd.fill('#username', 'local-admin'); await pd.fill('#password', 'x')
  const r403 = []
  pd.on('response', (re) => { if (re.url().endsWith('/api/auth/login')) r403.push(re.status()) })
  await pd.click('button[type="submit"]'); await wait(1500)
  E.checks.LG3_403 = await pd.evaluate(() => {
    const err = document.querySelector('#login-credential-error') || document.querySelector('[role="alert"]')
    return { alert: err ? err.textContent.trim() : null }
  })
  E.checks.LG3_403.http = r403[0] ?? null
  await s(pd, 'login-403-detail-desktop')

  // D-7 focus ring (desktop)
  await pd.evaluate(() => document.querySelectorAll('#username,#password').forEach((el) => el.blur()))
  await pd.focus('#username')
  E.checks.focus_ring = await pd.evaluate(() => {
    const el = document.activeElement, cs = getComputedStyle(el)
    return { id: el.id, outline: cs.outline, boxShadow: cs.boxShadow, webkitTapHighlight: cs.webkitTapHighlightColor }
  })
  await s(pd, 'login-focus-desktop')

  // ---------- SYSTEMS ----------
  attach(pd, 'systems-desktop'); await pd.goto(BASE + '/systems', { waitUntil: 'domcontentloaded' }); await wait(1200)
  const sysResp = []
  pd.on('response', (re) => { const u = re.url().replace(BASE, ''); if (u.startsWith('/api/')) sysResp.push(`${re.status()} ${re.request().method()} ${u}`) })
  await pd.waitForFunction(() => /Connected|Reconnecting/.test(document.body.innerText), { timeout: 8000 }).catch(() => {})
  E.checks.SY2 = await pd.evaluate(() => {
    const badge = document.querySelector('[role="status"][aria-label*="Real-time"], [role="status"]')
    return {
      badge_aria: badge ? badge.getAttribute('aria-label') : null,
      badge_text: badge ? badge.textContent.trim() : null,
      rows: [...document.querySelectorAll('tbody tr, main li, [class*="card"]')].slice(0, 8).map((r) => r.textContent.replace(/\s+/g, ' ').trim().slice(0, 80)),
      body_names: /nervecenter-api/.test(document.body.innerText) && /postgres/.test(document.body.innerText) && /nats/.test(document.body.innerText),
      alert_banner: document.querySelector('main [role="alert"]')?.textContent.trim() || null,
    }
  })
  E.api.systems_network = sysResp
  await wait(800); await s(pd, 'systems-desktop')

  // ---------- AGENTS ----------
  attach(pd, 'agents-desktop'); await pd.goto(BASE + '/agents', { waitUntil: 'domcontentloaded' }); await wait(1400)
  E.checks.AG2 = await pd.evaluate(() => {
    const dot = document.querySelector('[data-testid="agent-status"]')
    if (!dot) return null
    const card = dot.closest('main li, [class*="card"], article, div')
    const img = dot.closest('[role="img"]') || dot
    return { visible_text: dot.textContent.trim(), aria_label: img.getAttribute('aria-label') || null,
      role_img: !!document.querySelector('[data-testid="agent-status"] [role="img"], [role="img"]'),
      has_visible_status_word: /active|paused|error/.test(dot.textContent) }
  })
  const beforeCount = await pd.evaluate(() => document.querySelectorAll('.card, main li, [class*="rounded"]').length)
  await s(pd, 'agents-desktop')
  E.checks.AG2_before_rowcount = await pd.evaluate(() => document.body.innerText.match(/\nactive\n/g)?.length)
  const addBtnVisible = await pd.getByRole('button', { name: /add agent/i }).count()
  await pd.getByRole('button', { name: /add agent/i }).click(); await wait(500)
  const formVisible = await pd.locator('[data-testid="agent-form"]').count()
  if (formVisible) {
    await pd.fill('[data-testid="agent-form-name"]', 'audit-r3-probe')
    await pd.selectOption('[data-testid="agent-form-type"]', { index: 1 }).catch(() => {})
    await pd.fill('[data-testid="agent-form-description"]', 'R3 audit probe — walk recapture (safe to delete).')
  }
  await s(pd, 'agents-add-open-desktop')
  await s(pd, 'agents-add-form-desktop')
  E.checks.AG3_form_open = formVisible > 0
  E.checks.AG3_form_open_addBtn = addBtnVisible > 0
  const agPosts = []
  pd.on('response', (re) => { if (re.url().replace(BASE, '').startsWith('/api/agents') && re.request().method() === 'POST') agPosts.push(re.status()) })
  if (formVisible) {
    await pd.click('[data-testid="agent-form-submit"]'); await wait(2200)
  }
  E.checks.AG3 = {
    post_status: agPosts[0] ?? null,
    success_banner: await pd.locator('[data-testid="agent-form-success"]').count() ? (await pd.locator('[data-testid="agent-form-success"]').textContent()).trim() : null,
    error_banner: await pd.locator('[data-testid="agent-form-error"]').count() ? (await pd.locator('[data-testid="agent-form-error"]').textContent()).trim() : null,
    probe_visible: (await pd.getByText('audit-r3-probe').count()) > 0,
    rows_after: await pd.evaluate(() => document.body.innerText.match(/\nactive\n/g)?.length),
  }
  await s(pd, 'agents-add-result-desktop')

  // ---------- TASKS (real create via API with dependency) ----------
  const ta = await api('POST', '/api/tasks/', { title: 'R3 walk task A', description: 'r3 audit', status: 'pending', priority: 1, dependencies: [] })
  const aId = JSON.parse(ta.body).data?.id || JSON.parse(ta.body).id
  const tb = await api('POST', '/api/tasks/', { title: 'R3 walk task B', description: 'depends on A', status: 'pending', priority: 1, dependencies: aId ? [aId] : [] })
  E.api.task_create = { a: ta.status, b: tb.status, aId: !!aId, b_title: (JSON.parse(tb.body).data || {}).title }
  attach(pd, 'tasks-desktop'); await pd.goto(BASE + '/tasks', { waitUntil: 'domcontentloaded' }); await wait(1800)
  E.checks.TA = await pd.evaluate(() => ({
    edges: [...document.querySelectorAll('[data-testid^="task-edge-"]')].map((e) => e.getAttribute('data-testid')),
    nodes: [...document.querySelectorAll('[data-testid^="task-node-"]')].map((n) => n.getAttribute('data-testid')),
    has_svg: !!document.querySelector('[data-testid="task-dag-svg"] svg, svg'),
    body_has_A: document.body.innerText.includes('R3 walk task A'),
    body_has_B: document.body.innerText.includes('R3 walk task B'),
    status_badges: [...document.querySelectorAll('span,div')].filter((el) => /pending|running|done|failed/.test(el.textContent) && el.childElementCount === 0).slice(0, 6).map((el) => el.textContent.trim()),
  }))
  await s(pd, 'tasks-dag')
  await s(pd, 'tasks-dag-desktop')
  E.api.task_list_status = (await (await fetch(BASE + '/api/tasks/')).status)

  // ---------- GOALS (create END-TO-END in UI) ----------
  attach(pd, 'goals-desktop'); await pd.goto(BASE + '/goals', { waitUntil: 'domcontentloaded' }); await wait(1400)
  E.checks.GL_existing = await pd.evaluate(() => ({
    cards: [...document.querySelectorAll('[data-testid^="goal-card-"]')].map((c) => c.textContent.replace(/\s+/g, ' ').trim().slice(0, 200)),
    has_smoke_goal: document.body.innerText.includes('smoke-goal'),
  }))
  const newBtn = await pd.getByRole('button', { name: /new goal/i }).count()
  await pd.getByRole('button', { name: /new goal/i }).click(); await wait(400)
  const goalFormOpen = await pd.locator('#goal-title').count()
  await s(pd, 'goals-create-open')
  if (goalFormOpen) {
    await pd.fill('#goal-title', 'R3 walk goal')
    const desc = await pd.locator('#goal-description').count()
    if (desc) await pd.fill('#goal-description', 'Final recapture audit goal (safe to delete).')
    await pd.fill('#goal-priority', '1')
    await pd.fill('#goal-deadline', '2026-11-30')
  }
  const goalPosts = []
  pd.on('response', (re) => { if (re.url().replace(BASE, '').startsWith('/api/goals') && re.request().method() === 'POST')
    goalPosts.push({ status: re.status(), body: JSON.parse(re.request().postData() || '{}') }) })
  if (goalFormOpen) {
    await pd.getByRole('button', { name: /create/i }).last().click(); await wait(2400)
  }
  E.checks.GL1 = {
    button_visible: newBtn > 0, form_open: goalFormOpen > 0,
    post: goalPosts[0] || null,
    card_visible: (await pd.getByText('R3 walk goal').count()) > 0,
    cards_after: await pd.evaluate(() => [...document.querySelectorAll('[data-testid^="goal-card-"]')].map((c) => c.textContent.replace(/\s+/g, ' ').trim().slice(0, 160))),
  }
  await s(pd, 'goals-after-create')
  await s(pd, 'goals')
  E.api.goals_list_status = (await (await fetch(BASE + '/api/goals/')).status)

  // D-4: SVG icons + aria-current across nav
  E.checks.D4 = await pd.evaluate(() => {
    const nav = document.querySelector('nav')
    return {
      svg_icons: nav ? nav.querySelectorAll('svg').length : 0,
      emoji: nav ? /\p{Extended_Pictographic}/u.test(nav.textContent) : null,
      aria_current: nav ? [...nav.querySelectorAll('[aria-current]')].map((a) => `${a.textContent.trim().slice(0, 20)}=${a.getAttribute('aria-current')}`) : [],
      nav_text: nav ? nav.textContent.replace(/\s+/g, ' ').trim().slice(0, 200) : null,
    }
  })

  /* ================= MOBILE 390 ================= */
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 })
  const pm = await mctx.newPage()

  // ---------- LOGIN mobile ----------
  attach(pm, 'login-mobile'); await pm.goto(BASE + '/login', { waitUntil: 'load' }); await wait(900)
  E.checks.LG1_scan.mobile_text = /default credential/i.test(await pm.evaluate(() => document.body.innerText))
  E.checks.m_login_metrics = await pm.evaluate(() => {
    const form = document.querySelector('form')
    return { form_width: form ? Math.round(form.getBoundingClientRect().width) : null, vw: window.innerWidth,
      hscroll: document.documentElement.scrollWidth > window.innerWidth }
  })
  await s(pm, 'login-mobile')
  await pm.locator('#username').tap(); await wait(250)
  E.checks.focus_ring_mobile = await pm.evaluate(() => {
    const el = document.activeElement, cs = getComputedStyle(el)
    return { tag: el.tagName, outline: cs.outline, boxShadow: cs.boxShadow, webkitTapHighlight: cs.webkitTapHighlightColor }
  })
  await s(pm, 'login-focus-mobile')

  // ---------- OVERVIEW mobile + hamburger ----------
  attach(pm, 'overview-mobile'); await pm.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.checks.m_overview = await pm.evaluate(() => ({
    hscroll: document.documentElement.scrollWidth > window.innerWidth,
    scroll_w: document.documentElement.scrollWidth, inner_w: window.innerWidth,
    tiles: [...document.querySelectorAll('main [class*="grid"] > *')].slice(0, 8).map((t) => t.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)),
    body: document.body.innerText.replace(/\s+/g, ' ').slice(0, 260),
  }))
  await s(pm, 'overview')
  await s(pm, 'overview-hamburger')
  const burger = await pm.locator('header button[aria-label*="menu" i], header button[aria-label*="navigation" i], nav >> nth=0').first().count()
  const burgerBtn = await pm.locator('button[aria-label*="menu" i], button[aria-expanded]').first().count()
  if (burgerBtn) {
    const ariaBefore = await pm.locator('button[aria-expanded]').first().getAttribute('aria-expanded')
    await pm.locator('button[aria-expanded]').first().click(); await wait(400)
    E.checks.m_hamburger = { aria_before: ariaBefore, aria_after: await pm.locator('button[aria-expanded]').first().getAttribute('aria-expanded'),
      nav_visible: await pm.evaluate(() => document.querySelector('nav')?.getBoundingClientRect().height || 0) }
    await s(pm, 'overview-nav-open')
  } else {
    E.checks.m_hamburger = null
  }
  await wait(400); await s(pm, 'overview')

  // ---------- SYSTEMS mobile badge ----------
  attach(pm, 'systems-mobile'); await pm.goto(BASE + '/systems', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.checks.m_badge = await pm.evaluate(() => {
    const b = document.querySelector('[role="status"]')
    return { text: b ? b.textContent.trim() : null,
      hscroll: document.documentElement.scrollWidth > window.innerWidth }
  })
  await s(pm, 'systems-badge')
  await s(pm, 'systems')
  if (E.checks.m_badge && /connected/i.test(E.checks.m_badge.text || '')) await s(pm, 'systems-connected')

  // ---------- AGENTS mobile ----------
  attach(pm, 'agents-mobile'); await pm.goto(BASE + '/agents', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.checks.m_agents = { hscroll: await pm.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    has_probe: (await pm.getByText('audit-r3-probe').count()) > 0 }
  await s(pm, 'agents')

  // ---------- TASKS mobile ----------
  attach(pm, 'tasks-mobile'); await pm.goto(BASE + '/tasks', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.checks.m_tasks = { hscroll: await pm.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    has_A: await pm.evaluate(() => document.body.innerText.includes('R3 walk task A')) }
  await s(pm, 'tasks')

  // ---------- GOALS mobile ----------
  attach(pm, 'goals-mobile'); await pm.goto(BASE + '/goals', { waitUntil: 'domcontentloaded' }); await wait(1500)
  E.checks.m_goals = { hscroll: await pm.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
    has_r3: (await pm.getByText('R3 walk goal').count()) > 0 }
  await s(pm, 'goals')
  const mn = await pm.getByRole('button', { name: /new goal/i }).count()
  if (mn) { await pm.getByRole('button', { name: /new goal/i }).first().click(); await wait(400) }
  await s(pm, 'goals-create-open')

  browser.close()
  fs.writeFileSync(path.join(__dirname, 'walk-r3-final.json'), JSON.stringify(E, null, 2))
  console.log('WROTE', path.join(__dirname, 'walk-r3-final.json'))
  console.log(JSON.stringify({ shots: E.shots, checks: E.checks, api: E.api }, null, 1).slice(0, 6000))
}

main().catch((e) => { console.error('FATAL', e); process.exit(2) })
