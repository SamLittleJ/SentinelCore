import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@/test/server'

import { ApiError, apiRequest, CSRF_COOKIE, CSRF_HEADER } from './api'

function captureRequests() {
  const seen: Request[] = []
  server.use(
    http.all('/api/echo', ({ request }) => {
      seen.push(request.clone())
      return HttpResponse.json({ ok: true })
    }),
  )
  return seen
}

describe('apiRequest', () => {
  it('sends the CSRF token on requests that change state', async () => {
    document.cookie = `${CSRF_COOKIE}=token-123; path=/`
    const seen = captureRequests()

    await apiRequest('/echo', { method: 'POST', body: { a: 1 } })

    expect(seen[0].headers.get(CSRF_HEADER)).toBe('token-123')
    expect(seen[0].headers.get('Content-Type')).toBe('application/json')
    expect(await seen[0].json()).toEqual({ a: 1 })
  })

  it.each(['GET', 'HEAD'])('does not send the CSRF token on %s', async (method) => {
    document.cookie = `${CSRF_COOKIE}=token-123; path=/`
    const seen = captureRequests()

    await apiRequest('/echo', { method }).catch(() => undefined)

    expect(seen[0].headers.get(CSRF_HEADER)).toBeNull()
  })

  it('omits the header when there is no CSRF cookie', async () => {
    const seen = captureRequests()

    await apiRequest('/echo', { method: 'DELETE' })

    expect(seen[0].headers.get(CSRF_HEADER)).toBeNull()
  })

  it('throws ApiError with the detail and Retry-After', async () => {
    server.use(
      http.post('/api/locked', () =>
        HttpResponse.json(
          { detail: 'Too many failed login attempts. Try again later.' },
          { status: 429, headers: { 'Retry-After': '540' } },
        ),
      ),
    )

    const error = await apiRequest('/locked', { method: 'POST' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 429,
      detail: 'Too many failed login attempts. Try again later.',
      retryAfterSeconds: 540,
    })
  })

  it('handles errors without a JSON body', async () => {
    server.use(http.get('/api/broken', () => new HttpResponse('Bad gateway', { status: 502 })))

    const error = await apiRequest('/broken').catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 502, detail: null, retryAfterSeconds: null })
  })

  it('returns undefined for 204 responses', async () => {
    server.use(http.post('/api/empty', () => new HttpResponse(null, { status: 204 })))

    await expect(apiRequest('/empty', { method: 'POST' })).resolves.toBeUndefined()
  })
})
