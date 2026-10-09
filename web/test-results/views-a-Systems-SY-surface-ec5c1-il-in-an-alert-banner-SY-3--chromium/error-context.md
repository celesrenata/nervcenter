# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: views-a.spec.ts >> Systems (SY) >> surfaces the 501 detail in an alert banner (SY-3)
- Location: tests/e2e/views-a.spec.ts:207:3

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
  - heading "Systems" [level=1]
  - 'status "Real-time connection: Connecting"': "Real-time: Connecting"
  - 'img "nervecenter-api status: healthy"'
  - text: nervecenter-api 0.1.0 healthy
  - paragraph: API service is up and answering requests
```

# Test source

```ts
  119 |     await page.route('**/api/tasks', (r) => fulfillList(r, []))
  120 |     await page.route('**/api/incidents', (r) => fulfillList(r, []))
  121 | 
  122 |     try {
  123 |       await visitAuthenticated(page, '/')
  124 | 
  125 |       // The four live stat tiles remain.
  126 |       for (const label of ['Active Goals', 'Active Agents', 'Pending Tasks', 'Active Incidents']) {
  127 |         await expect(page.getByText(label)).toBeVisible()
  128 |       }
  129 | 
  130 |       // Real data flows into the panels (not hardcoded placeholders).
  131 |       await expect(page.getByText('Make pipeline production ready')).toBeVisible()
  132 |       await expect(page.getByText('investigator-1')).toBeVisible()
  133 | 
  134 |       // The OV-2 hardcodes are gone.
  135 |       expect(await page.getByText('Goal 1', { exact: true }).count()).toBe(0)
  136 |       expect(await page.getByText('Goal 2', { exact: true }).count()).toBe(0)
  137 |       expect(await page.getByText('Goal 3', { exact: true }).count()).toBe(0)
  138 |       expect(await page.getByText('Status: In Progress', { exact: true }).count()).toBe(0)
  139 | 
  140 |       assertConsoleClean(cap)
  141 |     } finally {
  142 |       detach()
  143 |     }
  144 |   })
  145 | 
  146 |   test('shows alert banner with status — detail when an endpoint rejects', async ({ page }) => {
  147 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  148 |     const detach = attachConsoleCapture(page, cap)
  149 | 
  150 |     await page.route('**/api/goals', (r) => fulfillList(r, []))
  151 |     await page.route('**/api/agents', (r) => fulfillList(r, []))
  152 |     await page.route('**/api/tasks', (r) =>
  153 |       fulfillList(r, { detail: 'tasks service error: missing column' }, 500),
  154 |     )
  155 |     await page.route('**/api/incidents', (r) => fulfillList(r, []))
  156 | 
  157 |     try {
  158 |       await visitAuthenticated(page, '/')
  159 | 
  160 |       const alert = page.getByRole('alert')
  161 |       await expect(alert).toBeVisible()
  162 |       const text = await alert.textContent()
  163 |       expect(text).toContain('500')
  164 |       expect(text).toContain('—')
  165 |       // OV-1: the failing tile is no longer a silent zero — the banner is shown.
  166 |       assertConsoleClean(cap)
  167 |     } finally {
  168 |       detach()
  169 |     }
  170 |   })
  171 | })
  172 | 
  173 | test.describe('Systems (SY)', () => {
  174 |   test('shows honest connection badge (text + aria-label), never a bare dot', async ({ page }) => {
  175 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  176 |     const detach = attachConsoleCapture(page, cap)
  177 | 
  178 |     await page.route('**/api/systems', (r) =>
  179 |       fulfillList(r, [
  180 |         { name: 'nervecenter-api', status: 'healthy', version: '0.4.1', message: 'OK', checkedAt: '2026-10-08T00:00:00Z' },
  181 |         { name: 'lavalink', status: 'degraded', version: '4.2.1', message: 'monitoring', checkedAt: '2026-10-08T00:00:00Z' },
  182 |       ]),
  183 |     )
  184 | 
  185 |     try {
  186 |       await visitAuthenticated(page, '/systems')
  187 | 
  188 |       // Real system rows render from the endpoint.
  189 |       await expect(page.getByText('nervecenter-api')).toBeVisible()
  190 |       await expect(page.getByText('lavalink')).toBeVisible()
  191 | 
  192 |       // The connection badge is real: it carries visible text and an aria-label.
  193 |       const badge = page.getByRole('status', { name: /Real-time connection/i })
  194 |       await expect(badge).toBeVisible()
  195 |       const badgeText = (await badge.textContent()) ?? ''
  196 |       expect(badgeText).toContain('Real-time:')
  197 |       // Every state has a human label, not just a color.
  198 |       expect(
  199 |         /Connecting|Connected|Disconnected|Reconnecting/.test(badgeText),
  200 |       ).toBe(true)
  201 |       assertConsoleClean(cap)
  202 |     } finally {
  203 |       detach()
  204 |     }
  205 |   })
  206 | 
  207 |   test('surfaces the 501 detail in an alert banner (SY-3)', async ({ page }) => {
  208 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  209 |     const detach = attachConsoleCapture(page, cap)
  210 | 
  211 |     await page.route('**/api/systems', (r) =>
  212 |       fulfillList(r, { detail: 'Systems list endpoint requires the systems service to be wired.' }, 501),
  213 |     )
  214 | 
  215 |     try {
  216 |       await visitAuthenticated(page, '/systems')
  217 | 
  218 |       const alert = page.getByRole('alert')
> 219 |       await expect(alert).toBeVisible()
      |                           ^ Error: expect(locator).toBeVisible() failed
  220 |       const text = (await alert.textContent()) ?? ''
  221 |       expect(text).toContain('501')
  222 |       expect(text).toContain('—')
  223 |       assertConsoleClean(cap)
  224 |     } finally {
  225 |       detach()
  226 |     }
  227 |   })
  228 | })
  229 | 
  230 | test.describe('Task DAG (TA)', () => {
  231 |   test('renders dependency graph + concurrency badges from real id/title/status fields', async ({ page }) => {
  232 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  233 |     const detach = attachConsoleCapture(page, cap)
  234 | 
  235 |     // Real backend shape: `id`, `title`, lowercase `status`, `dependencies`.
  236 |     await page.route('**/api/tasks', (r) =>
  237 |       fulfillList(r, [
  238 |         { id: 't-1', title: 'Collect evidence', status: 'completed', priority: 5, dependencies: [] },
  239 |         { id: 't-2', title: 'Trace allocation', status: 'in_progress', priority: 9, dependencies: ['t-1'] },
  240 |         { id: 't-3', title: 'Rank hypotheses', status: 'pending', priority: 9, dependencies: ['t-2'] },
  241 |       ]),
  242 |     )
  243 | 
  244 |     try {
  245 |       await visitAuthenticated(page, '/tasks')
  246 | 
  247 |       // TA-3: names come from real `title` fields.
  248 |       await expect(page.getByText('Collect evidence')).toBeVisible()
  249 |       await expect(page.getByText('Trace allocation')).toBeVisible()
  250 | 
  251 |       // TA-2: dependency graph — SVG present with one edge per dependency.
  252 |       const svg = page.getByTestId('task-dag-svg')
  253 |       await expect(svg).toBeVisible()
  254 |       // Edges are zero-height horizontal SVG curves: Playwright's
  255 |       // toBeVisible treats a zero-area bounding box as "hidden", so assert
  256 |       // existence + a real `d` path (the intent: one edge per dependency).
  257 |       await expect(page.getByTestId('task-edge-t-1-t-2')).toHaveCount(1)
  258 |       await expect(
  259 |         page.getByTestId('task-edge-t-1-t-2'),
  260 |       ).toHaveAttribute('d', /^M /)
  261 |       await expect(page.getByTestId('task-edge-t-2-t-3')).toHaveCount(1)
  262 |       await expect(
  263 |         page.getByTestId('task-edge-t-2-t-3'),
  264 |       ).toHaveAttribute('d', /^M /)
  265 | 
  266 |       // Nodes render with normalized uppercase status badges.
  267 |       await expect(page.getByTestId('task-node-t-2')).toContainText('RUNNING')
  268 |       await expect(page.getByTestId('task-node-t-1')).toContainText('COMPLETED')
  269 | 
  270 |       // Concurrency badges aggregate live state.
  271 |       await expect(page.getByRole('status', { name: /Concurrency/ })).toBeVisible()
  272 |       const badgeTexts = await page.locator('[role=status]').allTextContents()
  273 |       expect(badgeTexts.join(' ')).toMatch(/1 running/i)
  274 |       assertConsoleClean(cap)
  275 |     } finally {
  276 |       detach()
  277 |     }
  278 |   })
  279 | })
  280 | 
  281 | test.describe('Goals (GL)', () => {
  282 |   test('shows empty-state guidance and create flow posts + refreshes', async ({ page }) => {
  283 |     const cap: ConsoleCapture = { errors: [], pageErrors: [], failedRequests: [] }
  284 |     const detach = attachConsoleCapture(page, cap)
  285 | 
  286 |     const newGoal = {
  287 |       id: 'goal-new',
  288 |       title: 'Reduce latency below 1s p95',
  289 |       status: 'active',
  290 |       progress: 0.1,
  291 |       deadline: '2026-12-01',
  292 |       priority: 3,
  293 |     }
  294 |     let created = false
  295 | 
  296 |     await page.route('**/api/goals', async (route) => {
  297 |       if (route.request().method() === 'POST') {
  298 |         created = true
  299 |         await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(newGoal) })
  300 |       } else {
  301 |         await fulfillList(route, created ? [newGoal] : [])
  302 |       }
  303 |     })
  304 | 
  305 |     try {
  306 |       await visitAuthenticated(page, '/goals')
  307 | 
  308 |       // GL-2: empty state has guidance beyond a bare count.
  309 |       await expect(page.getByText(/No goals yet/)).toBeVisible()
  310 | 
  311 |       // GL-1: "+ New Goal" opens a real form.
  312 |       await page.getByRole('button', { name: /New Goal/i }).click()
  313 |       const form = page.getByRole('form', { name: /Create a new goal/i })
  314 |       await expect(form).toBeVisible()
  315 | 
  316 |       await page.getByLabel('Name').fill('Reduce latency below 1s p95')
  317 |       await page.getByLabel('Priority (0–10)').fill('3')
  318 |       await page.getByLabel('Due date').fill('2026-12-01')
  319 | 
```