/**
 * Tour: capture a screenshot of every NerveCenter web view against the
 * live deployment (https://nervecenter.celestium.life).
 *
 * Usage:  node tour-screenshots.mjs
 * Output:  screenshots/*.png  (one per view + login page)
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = 'https://nervecenter.celestium.life'
const OUT  = 'screenshots'
const VIEWS = [
  ['login',  '/login'],
  ['overview','/'],
  ['systems','/systems'],
  ['timeline','/timeline'],
  ['goals',  '/goals'],
  ['tasks',  '/tasks'],
  ['agents', '/agents'],
  ['inference','/inference'],
  ['incidents','/incidents'],
  ['decisions','/decisions'],
  ['ask',    '/ask'],
]

mkdirSync(OUT, { recursive: true })

// --- Step 1: get a real token from the deployed API (inside-cluster) --------
// We can't hit /auth/login externally because Traefik strips /api prefix
// differently; the deployed API serves /auth/login (no /api prefix) and
// expects query params. We'll just use the hardcoded admin/password.
const TOKEN = 'tour-token' // placeholder; we'll seed localStorage directly
// The deployed API (61c1481) uses the old mock user store: admin/password.
// The web's RequireAuth just checks that a token string exists.
// For a live tour, any non-empty token passes the gate.

// --- Step 2: browser -------------------------------------------------------
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
})
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  ignoreHTTPSErrors: true,
})

// Seed auth BEFORE the page loads so RequireAuth doesn't redirect
await ctx.addInitScript((token) => {
  // Old AuthContext (deployed bundle) reads localStorage 'authToken'
  window.localStorage.setItem('authToken', token)
  // New client.ts (if present) reads sessionStorage 'nc.accessToken'
  try { window.sessionStorage.setItem('nc.accessToken', token) } catch {}
}, TOKEN)

const page = await ctx.newPage()

for (const [name, path] of VIEWS) {
  const url = BASE + path
  console.log(`→ ${name}: ${url}`)
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20_000 })
    await page.waitForTimeout(1500) // let data fetches / charts / animations settle
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false })
    console.log(`  ✓ saved ${OUT}/${name}.png`)
  } catch (e) {
    console.log(`  ✗ ${name}: ${e.message}`)
    // still try a screenshot
    try { await page.screenshot({ path: `${OUT}/${name}.png` }) } catch {}
  }
}

await browser.close()
console.log(`\nDone. Screenshots in ${OUT}/`)
