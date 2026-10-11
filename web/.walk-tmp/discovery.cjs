const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ headless: true });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 } });
  const p = await ctx.newPage();
  const routes = ['/', '/login','/overview','/systems','/agents','/tasks','/goals'];
  for (const r of routes) {
    try { await p.goto('http://127.0.0.1:8080' + r, { waitUntil: 'load', timeout: 20000 }); }
    catch (e) { console.log(r, 'NAV-ERR', String(e).slice(0,150)); continue; }
    await p.waitForTimeout(1500);
    try {
      const info = await p.evaluate(() => {
        const txt = (el) => el ? el.textContent.replace(/\s+/g,' ').trim().slice(0,260) : null;
        return {
          url: location.href, title: document.title,
          h1: txt(document.querySelector('h1')),
          navLinks: [...document.querySelectorAll('nav a')].map(a=>({t:a.textContent.trim().slice(0,24), href:a.getAttribute('href'), aria:a.getAttribute('aria-current')})),
          navSVGs: document.querySelectorAll('nav svg').length,
          buttons: [...document.querySelectorAll('main button, header button')].map(b=>b.textContent.trim().slice(0,36)).slice(0,24),
          inputs: [...document.querySelectorAll('main input, main select, main textarea')].map(i=>({id:i.id, ph:i.placeholder, type:i.type, aria:(i.getAttribute('aria-label')||'').slice(0,40)})).slice(0,14),
          alerts: [...document.querySelectorAll('[role=alert],[role=status]')].map(a=>a.textContent.trim().slice(0,90)),
          mainText: txt(document.querySelector('main')),
        };
      });
      console.log('=====', r, '=>', p.url());
      console.log(JSON.stringify(info));
    } catch (e) { console.log(r, 'EVAL-ERR', String(e).slice(0,200)); }
  }
  await b.close();
})().catch(e => { console.error('FATAL', e); process.exit(2); });
