/* verify-shots.cjs — confirm walk-* PNGs are fresh + non-blank. */
const fs = require('fs')
const dir = __dirname + '/../screenshots/audit-live-r2'
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.png')).sort()
const blank = [], old = []
for (const f of files) {
  const s = fs.statSync(dir + '/' + f)
  if (s.size < 8000) blank.push(`${f} (${s.size}B)`)
  if (Date.now() - s.mtimeMs > 12 * 3600 * 1000) old.push(f)
}
console.log('TOTAL', files.length, 'PNGs')
console.log('BLANK:', blank.join(', ') || 'none')
console.log('STALE (>12h):', old.join(', ') || 'none')
const canon = ['login-desktop', 'login-mobile', 'login-error-desktop', 'login-403-detail-desktop', 'login-focus-mobile', 'overview-desktop', 'overview-mobile', 'overview-mobile-hamburger-closed', 'overview-mobile-nav-open', 'systems-desktop', 'systems-badge-mobile', 'agents-desktop', 'agents-mobile', 'agents-add-open-desktop', 'agents-add-form-desktop', 'agents-add-result-desktop', 'tasks-dag-desktop', 'tasks-mobile', 'tasks-desktop', 'goals-create-open-desktop', 'goals-mobile', 'goals-create-mobile']
for (const c of canon) {
  const p = dir + '/' + c + '.png'
  if (!fs.existsSync(p)) { console.log('MISSING', c); continue }
  const s = fs.statSync(p)
  console.log(c + '.png', s.size + 'B', 'fresh=' + (Date.now() - s.mtimeMs < 12 * 3600 * 1000))
}
