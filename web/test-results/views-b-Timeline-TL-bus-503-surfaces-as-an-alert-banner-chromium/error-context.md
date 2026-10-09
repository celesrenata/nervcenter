# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: views-b.spec.ts >> Timeline (TL) >> bus 503 surfaces as an alert banner
- Location: tests/e2e/views-b.spec.ts:324:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('alert')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('alert') with timeout 5000ms
  - waiting for getByRole('alert')

```

```yaml
- heading "NerveCenter" [level=1]
- paragraph: Personal Intelligence Core
- navigation:
  - link "Overview":
    - /url: /
  - link "Systems":
    - /url: /systems
  - link "Timeline":
    - /url: /timeline
  - link "Goals":
    - /url: /goals
  - link "Task DAG":
    - /url: /tasks
  - link "Agents":
    - /url: /agents
  - link "Inference":
    - /url: /inference
  - link "Incidents":
    - /url: /incidents
  - link "Decisions":
    - /url: /decisions
  - link "Ask":
    - /url: /ask
- paragraph: Guest
- paragraph: No roles
- button "Logout"
- main:
  - heading "Timeline" [level=1]
  - heading "Recent events" [level=3]
  - paragraph: No events recorded yet.
  - paragraph: The event bus has not published any activity (or is not configured). Events are append-only and appear here the moment the system records them — nothing is hidden.
  - heading "Legend" [level=3]
  - text: info warning error success
```

# Test source

```ts
  236 |   })
  237 | })
  238 | 
  239 | test.describe('Decisions (DC)', () => {
  240 |   test('rejected fetch shows role=alert `status — detail`, not a silent empty list (DC-1)', async ({ page }) => {
  241 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  242 |     const detach = attachConsoleCapture(page, cap)
  243 | 
  244 |     await page.route('**/api/decisions', (r) =>
  245 |       fulfillError(r, 501, 'Decision listing is not implemented on this backend'),
  246 |     )
  247 | 
  248 |     try {
  249 |       await visitAuthenticated(page, '/decisions')
  250 | 
  251 |       const alert = page.getByRole('alert')
  252 |       await expect(alert).toBeVisible()
  253 |       const text = (await alert.textContent()) ?? ''
  254 |       expect(text).toContain('501')
  255 |       expect(text).toContain('—')
  256 |       expect(text).toContain('not implemented')
  257 | 
  258 |       // The silent empty-list state must NOT be shown on error.
  259 |       await expect(page.getByTestId('decisions-empty')).toHaveCount(0)
  260 | 
  261 |       assertConsoleClean(cap)
  262 |     } finally {
  263 |       detach()
  264 |     }
  265 |   })
  266 | 
  267 |   test('genuine no-data still renders the honest empty state', async ({ page }) => {
  268 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  269 |     const detach = attachConsoleCapture(page, cap)
  270 | 
  271 |     await page.route('**/api/decisions', (r) => fulfillJson(r, []))
  272 | 
  273 |     try {
  274 |       await visitAuthenticated(page, '/decisions')
  275 | 
  276 |       await expect(page.getByTestId('decisions-empty')).toBeVisible()
  277 |       await expect(page.getByRole('alert')).toHaveCount(0)
  278 |       assertConsoleClean(cap)
  279 |     } finally {
  280 |       detach()
  281 |     }
  282 |   })
  283 | })
  284 | 
  285 | test.describe('Timeline (TL)', () => {
  286 |   test('renders real events from GET /api/events; hardcoded samples are gone (TL-1)', async ({ page }) => {
  287 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  288 |     const detach = attachConsoleCapture(page, cap)
  289 | 
  290 |     await page.route('**/api/events', (r) =>
  291 |       fulfillJson(r, {
  292 |         data: [
  293 |           {
  294 |             id: 'ev-1',
  295 |             event_type: 'task_state_change',
  296 |             category: 'task',
  297 |             occurred_at: '2026-10-08T05:00:00Z',
  298 |             subject: 't-042',
  299 |             payload: { message: 'Task t-042 entered VERIFYING' },
  300 |             severity: 'info',
  301 |           },
  302 |         ],
  303 |         meta: { pagination: { total: 1, page: 1, per_page: 1 } },
  304 |       }),
  305 |     )
  306 | 
  307 |     try {
  308 |       await visitAuthenticated(page, '/timeline')
  309 | 
  310 |       // Real event content from the API.
  311 |       await expect(page.getByText('Task t-042 entered VERIFYING')).toBeVisible()
  312 |       await expect(page.getByText('task_state_change')).toBeVisible()
  313 | 
  314 |       // The round-1 hardcoded fixtures must be gone.
  315 |       await expect(page.getByText('Agent "data-processor" started successfully')).toHaveCount(0)
  316 |       await expect(page.getByText('Task "data-sync" completed in 45s')).toHaveCount(0)
  317 | 
  318 |       assertConsoleClean(cap)
  319 |     } finally {
  320 |       detach()
  321 |     }
  322 |   })
  323 | 
  324 |   test('bus 503 surfaces as an alert banner', async ({ page }) => {
  325 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  326 |     const detach = attachConsoleCapture(page, cap)
  327 | 
  328 |     await page.route('**/api/events', (r) =>
  329 |       fulfillError(r, 503, 'event bus unreachable: stream not found'),
  330 |     )
  331 | 
  332 |     try {
  333 |       await visitAuthenticated(page, '/timeline')
  334 | 
  335 |       const alert = page.getByRole('alert')
> 336 |       await expect(alert).toBeVisible()
      |                           ^ Error: expect(locator).toBeVisible() failed
  337 |       const text = (await alert.textContent()) ?? ''
  338 |       expect(text).toContain('503')
  339 |       expect(text).toContain('—')
  340 |       expect(text).toContain('event bus unreachable')
  341 |       assertConsoleClean(cap)
  342 |     } finally {
  343 |       detach()
  344 |     }
  345 |   })
  346 | 
  347 |   test('empty bus shows honest guidance copy', async ({ page }) => {
  348 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  349 |     const detach = attachConsoleCapture(page, cap)
  350 | 
  351 |     await page.route('**/api/events', (r) => fulfillJson(r, { data: [], meta: {} }))
  352 | 
  353 |     try {
  354 |       await visitAuthenticated(page, '/timeline')
  355 | 
  356 |       const empty = page.getByTestId('timeline-empty')
  357 |       await expect(empty).toBeVisible()
  358 |       const text = (await empty.textContent()) ?? ''
  359 |       expect(text).toContain('No events recorded')
  360 |       assertConsoleClean(cap)
  361 |     } finally {
  362 |       detach()
  363 |     }
  364 |   })
  365 | })
  366 | 
  367 | test.describe('Inference (INF)', () => {
  368 |   test('each empty section renders guidance copy (INF-1)', async ({ page }) => {
  369 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  370 |     const detach = attachConsoleCapture(page, cap)
  371 | 
  372 |     await page.route('**/api/compute', (r) => fulfillJson(r, []))
  373 |     await page.route('**/api/routes', (r) => fulfillJson(r, []))
  374 |     await page.route('**/api/models/history', (r) => fulfillJson(r, []))
  375 | 
  376 |     try {
  377 |       await visitAuthenticated(page, '/inference')
  378 | 
  379 |       const nodes = page.getByTestId('inference-empty-nodes')
  380 |       const routes = page.getByTestId('inference-empty-routes')
  381 |       const history = page.getByTestId('inference-empty-history')
  382 | 
  383 |       await expect(nodes).toBeVisible()
  384 |       await expect(routes).toBeVisible()
  385 |       await expect(history).toBeVisible()
  386 | 
  387 |       expect((await nodes.textContent()) ?? '').toContain('No compute nodes')
  388 |       expect((await routes.textContent()) ?? '').toContain('No OmniRoute routes')
  389 |       expect((await history.textContent()) ?? '').toContain('No model history')
  390 | 
  391 |       assertConsoleClean(cap)
  392 |     } finally {
  393 |       detach()
  394 |     }
  395 |   })
  396 | })
  397 | 
  398 | test.describe('Agents (AG)', () => {
  399 |   test('status carries text + aria-label, never a bare dot (AG-2)', async ({ page }) => {
  400 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  401 |     const detach = attachConsoleCapture(page, cap)
  402 | 
  403 |     await page.route('**/api/agents', (r) =>
  404 |       fulfillJson(r, [
  405 |         {
  406 |           id: 'agent-1',
  407 |           name: 'investigator-1',
  408 |           type: 'investigator',
  409 |           status: 'active',
  410 |           lastHeartbeat: '2026-10-08T05:55:00Z',
  411 |           cpuUsage: 12,
  412 |           memoryUsage: 34,
  413 |           tasksCompleted: 120,
  414 |           tasksFailed: 3,
  415 |         },
  416 |         {
  417 |           id: 'agent-2',
  418 |           name: 'deployer-1',
  419 |           type: 'operator',
  420 |           status: 'paused',
  421 |           lastHeartbeat: '2026-10-08T04:00:00Z',
  422 |           cpuUsage: 0,
  423 |           memoryUsage: 8,
  424 |           tasksCompleted: 40,
  425 |           tasksFailed: 0,
  426 |         },
  427 |       ]),
  428 |     )
  429 | 
  430 |     try {
  431 |       await visitAuthenticated(page, '/agents')
  432 | 
  433 |       await expect(page.getByText('investigator-1')).toBeVisible()
  434 |       await expect(page.getByText('deployer-1')).toBeVisible()
  435 | 
  436 |       // Every status has visible text…
```