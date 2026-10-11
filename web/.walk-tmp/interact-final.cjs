/* FINAL [interact] recapture against deployed TAG bee3fa8 (port-forward :18321).
   Desktop 1280x800 + Mobile 390x844. Outputs:
   - screenshots OVERWRITE web/screenshots/audit-live-r2/interact-*.png
   - evidence JSON -> web/.walk-tmp/interact-final.json
   Run: (cd web && node .walk-tmp/interact-final.cjs) */
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

const BASE = 'http://127.0.0.1:18321'
const SHOTS = path.resolve(__dirname, '../screenshots/audit-live-r2')
const E = {
  bundle: null,
  perView: {},
  shots: [],
  checks: {},
  apiStatus: {},
  consoleErrors: {},
  reqFailed: {},
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

async function shot(page, name) {
  const p = path.join(SHOTS, name + '.png')
  await page.screenshot({ path: p, type: 'png' })
  const sz = fs.statSync(p).size
  E.shots.push({ name, size: sz, blank: sz < 8000 })
  return p
}

async function shotEl(el, name) {
  const p = path.join(SHOTS, name + '.png')
  await el.screenshot({ path: p })
  const sz = fs.statSync(p).size
  E.shots.push({ name, size: sz, blank: sz < 2000 })
  return p
}

function attach(page, view) {
  E.consoleErrors[view] = []
  E.reqFailed[view] = []
  E.apiStatus[view] = []
  page.on('console', (m) => m.type() === 'error' && E.consoleErrors[view].push(m.text().slice(0, 300)))
  page.on('requestfailed', (rq) =>
    E.reqFailed[view].push(`${rq.method()} ${rq.url().slice(0, 200)} :: ${rq.failure()?.errorText || 'no response'}`))
  page.on('response', (r) => {
    const u = r.url()
    if (u.includes('/api/')) {
      E.apiStatus[view].push(`${r.status()} ${r.request().method()} ${u.replace(BASE, '')}`)
      if (r.status() >= 400) E.reqFailed[view].push(`${r.status()} ${r.request().method()} ${u.replace(BASE, '')}`)
    }
  })
}

/* incident card locator: card > flex-row > left-div > h3 */
const card = (page, title) =>
  page.locator('div.rounded-lg.shadow-lg').filter({ has: page.locator('h3', { hasText: title }) }).first()

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })

  // ---------- DESKTOP ----------
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await ctx.newPage()

  // bundle identity
  const homeHtml = await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
  E.bundle = ((await homeHtml.text()).match(/assets\/[A-Za-z0-9._-]+\.js/) || [null])[0]

  // ===== INCIDENTS =====
  attach(page, 'incidents')
  await page.goto(BASE + '/incidents', { waitUntil: 'networkidle' })
  await page.locator('h1:has-text("Incidents")').waitFor()
  await wait(700)
  E.checks.incidentsRows = await page.locator('div.rounded-lg.shadow-lg h3').allTextContents()
  E.checks.incidentsClosedNoActions = await card(page, 'smoke incident')
    .locator('button:has-text("Resolve"), button:has-text("Close")')
    .count()
  await shot(page, 'interact-incidents-desktop')

  // IN-1: Report Incident -> POST /api/incidents 201 -> row appears
  const newTitle = `Final r2 interact probe ${new Date().toISOString().slice(11, 16)} (bee3fa8)`
  await page.getByRole('button', { name: '+ Report Incident' }).click()
  await page.locator('[data-testid="incident-form-title"]').fill(newTitle)
  await page.locator('[data-testid="incident-form-severity"]').selectOption('medium')
  await page.locator('[data-testid="incident-form-submit"]').click()
  await page.locator('[data-testid="incident-form-success"]').waitFor({ timeout: 10000 })
  E.checks.in1CreatedRowAppears = await card(page, newTitle).locator('h3').isVisible()
  await wait(500)

  // per-row controls on the fresh active row (Resolve + Close both visible)
  const freshCard = card(page, newTitle)
  E.checks.in1FreshRowResolveVisible = await freshCard.locator('button:has-text("Resolve")').isVisible()
  E.checks.in1FreshRowCloseVisible = await freshCard.locator('button:has-text("Close")').isVisible()
  await freshCard.scrollIntoViewIfNeeded()
  await shotEl(freshCard, 'interact-incidents-row-actions-desktop')

  // Transition race: second tab resolves the new incident; the first (stale) tab
  // still shows it as active, so its Resolve click is a genuine illegal
  // transition -> backend 409 -> verbatim detail must surface on the row.
  const page2 = await ctx.newPage()
  attach(page2, 'incidents-tab2')
  await page2.goto(BASE + '/incidents', { waitUntil: 'networkidle' })
  const c2 = card(page2, newTitle)
  await c2.locator('button:has-text("Resolve")').waitFor({ timeout: 10000 })
  await c2.locator('button:has-text("Resolve")').click()
  await c2.locator('span:has-text("resolved")').first().waitFor({ timeout: 10000 })
  E.checks.in1Resolve200 = true

  const staleCard = card(page, newTitle) // page 1 list still shows 'active'
  await staleCard.locator('button:has-text("Resolve")').click()
  const alert409 = staleCard.locator('[data-testid="incident-action-error"]')
  await alert409.waitFor({ timeout: 10000 })
  E.checks.in1_409Detail = (await alert409.textContent())?.trim()
  await staleCard.scrollIntoViewIfNeeded()
  await shotEl(staleCard, 'interact-incidents-409-desktop')
  await page2.close()

  // Terminal transition: close (200) -> row renders no actions
  await staleCard.locator('button:has-text("Close")').click()
  await staleCard.locator('span:has-text("closed")').first().waitFor({ timeout: 10000 })
  E.checks.in1ClosedNoActions = await staleCard.locator('button:has-text("Resolve"), button:has-text("Close")').count()

  // ===== DECISIONS (DC-1 + N4) =====
  attach(page, 'decisions')
  await page.goto(BASE + '/decisions', { waitUntil: 'networkidle' })
  await page.locator('[data-testid="decisions-error"]').waitFor({ timeout: 10000 })
  E.checks.dc1AlertText = (await page.locator('[data-testid="decisions-error"]').textContent())?.trim()
  const bodyText = await page.locator('body').innerText()
  E.checks.n4NoBareCountNextToError = !/total decisions/.test(bodyText)
  E.checks.dc1UnavailableBanner = await page.locator('[data-testid="decisions-unavailable"]').isVisible()
  await shot(page, 'interact-decisions-error-desktop')

  // ===== TIMELINE (TL-1: seeded real bus event renders) =====
  attach(page, 'timeline')
  await page.goto(BASE + '/timeline', { waitUntil: 'networkidle' })
  const seedEvent = page.locator('text=audit.timeline.seed')
  await seedEvent.waitFor({ timeout: 10000 })
  E.checks.tl1LiveEventRendered = (await seedEvent.count()) > 0
  E.checks.tl1SeedMessage = (await page.locator('text=TL-1 audit seed event').first().textContent().catch(() => null)) || null
  E.checks.tl1NoErrorAlert = (await page.locator('[data-testid="timeline-error"]').count()) === 0
  await shot(page, 'interact-timeline-desktop')

  // ===== ASK (202 pending renders) =====
  attach(page, 'ask')
  await page.goto(BASE + '/ask', { waitUntil: 'networkidle' })
  await page.locator('input[placeholder="Type your message..."]').fill('Final recapture: summarize current system health')
  await page.getByRole('button', { name: 'Send' }).click()
  const acceptedMsg = page.locator('text=Request accepted').first()
  await acceptedMsg.waitFor({ timeout: 15000 })
  E.checks.ask202PendingRendered = (await acceptedMsg.textContent())?.slice(0, 160)
  await wait(400)
  await shot(page, 'interact-ask-desktop')

  // ===== INFERENCE (INF-1 empty states; 501 handled as guidance, no red alert) =====
  attach(page, 'inference')
  await page.goto(BASE + '/inference', { waitUntil: 'networkidle' })
  await page.locator('[data-testid="inference-empty-history"]').waitFor({ timeout: 10000 })
  E.checks.inf1EmptyStates = [
    (await page.locator('[data-testid="inference-empty-nodes"]').count()) === 1,
    (await page.locator('[data-testid="inference-empty-routes"]').count()) === 1,
    (await page.locator('[data-testid="inference-empty-history"]').count()) === 1,
  ]
  E.checks.inf1NoRedAlert = (await page.locator('[role="alert"]').count()) === 0
  await shot(page, 'interact-inference-desktop')

  // ===== FOCUS RING + SVG + aria-current (desktop) =====
  attach(page, 'overview')
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  const sidebarLink = page.locator('nav#app-nav a[href="/systems"]').first()
  await sidebarLink.focus()
  const focusInfo = await page.evaluate(() => {
    const el = document.activeElement
    if (!el) return { focused: null }
    const cs = getComputedStyle(el)
    const rect = el.getBoundingClientRect()
    return {
      focused: el.textContent?.trim(),
      outline: `${cs.outlineStyle} ${cs.outlineWidth} ${cs.outlineColor}`,
      boxShadow: cs.boxShadow !== 'none' ? cs.boxShadow.slice(0, 90) : 'none',
      rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
    }
  })
  E.checks.focusRing = focusInfo
  const r = focusInfo.rect
  if (r) {
    await page.screenshot({
      path: path.join(SHOTS, 'interact-focus-ring-desktop.png'),
      clip: { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: Math.min(1280, r.w + 60), height: r.h + 16 },
    })
    E.shots.push({ name: 'interact-focus-ring-desktop', size: fs.statSync(path.join(SHOTS, 'interact-focus-ring-desktop.png')).size, blank: false })
  }
  E.checks.navSvgIcons = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('nav#app-nav a'))
    return {
      linksWithSvg: links.filter((a) => a.querySelector('svg')).length,
      linksTotal: links.length,
      ariaCurrent: Array.from(document.querySelectorAll('[aria-current="page"]')).map((a) => a.textContent?.trim()),
    }
  })

  // ================= MOBILE =================
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
  const mpage = await mctx.newPage()

  // ---- Incidents mobile ----
  attach(mpage, 'incidents-mobile')
  await mpage.goto(BASE + '/incidents', { waitUntil: 'networkidle' })
  await mpage.locator('h1:has-text("Incidents")').waitFor()
  await wait(700)
  E.checks.mobileIncidentsNoHscroll = await mpage.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  await shot(mpage, 'interact-incidents-mobile')

  // hamburger one-tap + clickable while open (walk-round fix)
  const burger = mpage.locator('button[aria-label="Open navigation"], button[aria-label="Close navigation"]').first()
  await burger.click()
  await wait(350)
  E.checks.mobileHamburgerOneTapOpens = (await mpage.locator('button[aria-expanded="true"]').count()) === 1
  await shot(mpage, 'interact-incidents-mobile-nav-open')
  const closeToggle = mpage.locator('button[aria-label="Close navigation"]').first()
  let closedAfterSecondTap
  if (await closeToggle.isVisible().catch(() => false)) {
    await closeToggle.click()
    await wait(350)
    closedAfterSecondTap = (await mpage.locator('button[aria-expanded="true"]').count()) === 0
  } else {
    closedAfterSecondTap = 'toggle-not-visible-while-open'
  }
  E.checks.mobileHamburgerClickableWhileOpen = closedAfterSecondTap
  E.checks.mobileDrawerOpenNoHscroll = await mpage.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)

  // ---- Decisions mobile ----
  attach(mpage, 'decisions-mobile')
  await mpage.goto(BASE + '/decisions', { waitUntil: 'networkidle' })
  await mpage.locator('[data-testid="decisions-error"]').waitFor({ timeout: 10000 })
  await shot(mpage, 'interact-decisions-error-mobile')

  // ---- Timeline mobile ----
  attach(mpage, 'timeline-mobile')
  await mpage.goto(BASE + '/timeline', { waitUntil: 'networkidle' })
  await mpage.locator('text=audit.timeline.seed').waitFor({ timeout: 10000 })
  E.checks.mobileTimelineLiveEvent = true
  await shot(mpage, 'interact-timeline-mobile')

  // ---- Ask mobile ----
  attach(mpage, 'ask-mobile')
  await mpage.goto(BASE + '/ask', { waitUntil: 'networkidle' })
  await mpage.locator('input[placeholder="Type your message..."]').fill('Mobile recapture check')
  await mpage.getByRole('button', { name: 'Send' }).click()
  await mpage.locator('text=Request accepted').first().waitFor({ timeout: 15000 })
  await wait(400)
  await shot(mpage, 'interact-ask-mobile')

  // ---- Inference mobile ----
  attach(mpage, 'inference-mobile')
  await mpage.goto(BASE + '/inference', { waitUntil: 'networkidle' })
  await mpage.locator('[data-testid="inference-empty-history"]').waitFor({ timeout: 10000 })
  E.checks.mobileInferenceNoHscroll = await mpage.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  await shot(mpage, 'interact-inference-mobile')

  // ---- content ratio on overview (mobile) ----
  attach(mpage, 'overview-mobile')
  await mpage.goto(BASE + '/', { waitUntil: 'networkidle' })
  E.checks.mobileContentRatio = await mpage.evaluate(() => {
    const vw = window.innerWidth
    const main = document.querySelector('main') || document.body
    const w = main.getBoundingClientRect().width
    return { viewport: vw, contentWidth: Math.round(w), pct: Math.round((w / vw) * 100) }
  })

  await browser.close()

  fs.writeFileSync(path.join(__dirname, 'interact-final.json'), JSON.stringify(E, null, 2))
  console.log(JSON.stringify({ shots: E.shots.length, checks: E.checks }, null, 2))
}

main().catch((e) => {
  console.error('SCRIPT FAIL:', e)
  process.exit(1)
})
