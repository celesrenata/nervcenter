/* fix-verify.cjs — verify the two in-repo Layout fixes on the DEV server
   (vite :3001, proxying /api to the live port-forward :8080).
   1. CC-4b: hamburger toggle stays clickable while the drawer is open.
   2. N-1: no "Logout" button for Guest (user === null).
   Screenshots → screenshots/audit-live-r2/dev-* (temp, removed after). */
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

const BASE = 'http://localhost:3001'
const SHOTS = path.resolve(__dirname, '../screenshots/audit-live-r2')
const R = { shots: [], checks: {} }
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 })
  const page = await ctx.newPage()
  const errs = []
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)))

  await page.goto(BASE + '/', { waitUntil: 'load' })
  await page.waitForTimeout(2200) // real data via proxy
  R.checks.data_loaded = await page.evaluate(() => document.body.innerText.includes('Active Goals'))

  // Guest footer: Logout must be ABSENT
  R.checks.N1_guest = await page.evaluate(() => ({
    hasLogout: [...document.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Logout'),
    footer_text: document.querySelector('.mt-auto')?.textContent.replace(/\s+/g, ' ').trim() || null,
  }))

  // CC-4b: open drawer, then click the HEADER toggle to close — must succeed fast
  const burger = page.locator('header button[aria-expanded]')
  await burger.click()
  await page.waitForTimeout(400)
  R.checks.cc4b_open = await page.evaluate(() => ({
    aria: document.querySelector('[aria-expanded="true"]')?.getAttribute('aria-label'),
    drawer_top: (() => { const d = document.querySelector('div[role="dialog"]'); return d ? d.getBoundingClientRect().top : null })(),
  }))
  const t0 = Date.now()
  await burger.click({ timeout: 5000 }) // fails on unfixed bundle (intercepted)
  await page.waitForTimeout(300)
  R.checks.cc4b_close = { ms: Date.now() - t0, ariaNow: await page.evaluate(() => document.querySelector('[aria-expanded="true"]')?.getAttribute('aria-label') || null) }
  const dialogClose = page.locator('div[role="dialog"] button[aria-label="Close navigation"]')
  // reopen, close via drawer button (regression check)
  await burger.click(); await page.waitForTimeout(300)
  await dialogClose.click({ timeout: 3000 }); await page.waitForTimeout(300)
  R.checks.cc4b_drawer_close_still_works = await page.evaluate(() => document.querySelector('[aria-expanded="true"]') === null)
  // Escape close
  await burger.click(); await page.waitForTimeout(300)
  await page.keyboard.press('Escape'); await page.waitForTimeout(300)
  R.checks.cc4b_escape_still_works = await page.evaluate(() => document.querySelector('[aria-expanded="true"]') === null)

  // No horizontal scroll + drawer height check (content below top-12 bar)
  R.checks.hscroll = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }))
  R.checks.drawer_height = await page.evaluate(() => {
    const d = document.querySelector('div[role="dialog"]')
    return d ? Math.round(d.getBoundingClientRect().height) : null
  })

  const shot = async (name) => {
    const p = path.join(SHOTS, name + '.png')
    await page.screenshot({ path: p, type: 'png' })
    R.shots.push({ name, size: fs.statSync(p).size })
  }
  await shot('dev-fix-cc4b-hamburger-open')
  await browser.close()
  fs.writeFileSync(path.join(__dirname, 'fix-verify.json'), JSON.stringify({ ...R, consoleErrors: errs }, null, 2))
  console.log('FIX-VERIFY', JSON.stringify({ ...R, consoleErrors: errs }, null, 1).slice(0, 2500))
})().catch((e) => { console.error('FATAL', e); process.exit(2) })
