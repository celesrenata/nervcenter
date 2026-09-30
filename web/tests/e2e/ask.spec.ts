import { expect, test } from '@playwright/test'

/**
 * AC005 — Ask round-trip against the REAL backend.
 *
 * Flow: seed auth → /ask → submit a question through the form →
 * the UI POSTs /api/context/ask, the dependency-free backend answers
 * HTTP 202 `{"accepted":true,"executed":false,"service":"context",
 * "request_id":…,"timestamp":…,"detail":…}` → AskView renders that
 * ack as a chat message ("Request accepted (execution: pending). …").
 *
 * Asserts both the wire response (status 202 + accepted/executed fields)
 * and exactly what the view renders from that payload, with zero console
 * errors. Same console-error policy as views.spec.ts (the only filter is
 * the two provable dead-end 404s — masked via `msg.location().url`, since
 * the console text carries no URL — neither of which fires on this route).
 */

const KNOWN_MISSING_BACKEND_PATHS = ['/api/systems', '/api/decisions']

test('Ask round-trip renders the /api/context/ask response without console errors', async ({
  page,
}) => {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  const failedRequests: string[] = []
  const onConsole = (msg: import('@playwright/test').ConsoleMessage) => {
    if (msg.type() !== 'error') return
    const text = msg.text()
    if (text.startsWith('Failed to load resource:')) {
      // The URL is NOT in the console text — it lives on msg.location().url.
      const url = msg.location()?.url ?? ''
      if (KNOWN_MISSING_BACKEND_PATHS.some((p) => url.endsWith(p))) return
    }
    consoleErrors.push(text)
  }
  page.on('console', onConsole)
  page.on('pageerror', (err) => pageErrors.push(err.message))
  page.on('requestfailed', (req) =>
    failedRequests.push(`${req.method()} ${req.url()}`),
  )

  try {
    await page.addInitScript(() => {
      localStorage.setItem('authToken', 'e2e-token')
    })
    await page.goto('/ask', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main h1')).toHaveText('Ask NerveCenter')

    // The greeting message is part of the initial render.
    await expect(page.getByText('Hello! I am NerveCenter. How can I help you today?')).toBeVisible()

    const question = 'What are my active goals?'
    const input = page.getByPlaceholder('Type your message...')
    await input.fill(question)

    const responsePromise = page.waitForResponse(
      (res) =>
        res.url().endsWith('/api/context/ask') && res.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Send' }).click()
    const response = await responsePromise

    // Wire assertions on the real backend's 202 ack.
    expect(response.status()).toBe(202)
    const body = await response.json()
    expect(body.accepted).toBe(true)
    expect(body.executed).toBe(false)
    expect(body.service).toBe('context')
    expect(typeof body.request_id).toBe('string')
    expect(typeof body.timestamp).toBe('string')

    // The user's question appears in the chat. Scope to the chat-bubble
    // paragraph: the same string also lives in the permanent "Quick
    // Questions" suggestion button below the chat, so a bare getByText
    // would hit two elements (strict-mode violation).
    const userBubble = page.locator('p.whitespace-pre-wrap', { hasText: question })
    await expect(userBubble.first()).toBeVisible()

    // What AskView actually renders from the 202 payload: the
    // accepted/executed-false ack, with no provenance block.
    const assistantText = page
      .locator('p')
      .filter({ hasText: 'Request accepted (execution: pending).' })
    await expect(assistantText).toBeVisible()
    await expect(assistantText).toHaveText(/Request accepted \(execution: pending\)\./)
    expect(body.detail).toBeTruthy()
    await expect(assistantText).toHaveText(new RegExp(body.detail!))

    // No Provenance section for an ack payload.
    await expect(page.getByText('Provenance')).toHaveCount(0)

    await page.waitForTimeout(500)
    expect(pageErrors, 'uncaught exceptions').toEqual([])
    expect(failedRequests, 'failed network requests').toEqual([])
    expect(consoleErrors, 'console errors').toEqual([])
  } finally {
    page.off('console', onConsole)
  }
})
