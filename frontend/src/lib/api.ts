// The Vite dev server (and the production reverse proxy) forwards /api to the
// backend, so requests stay on one origin and the session cookie is sent.
export const API_BASE = '/api'

// Set by the backend at browser login; readable on purpose so it can be
// echoed in a header. The session cookie itself is httpOnly.
export const CSRF_COOKIE = 'sentinelcore_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export class ApiError extends Error {
  readonly status: number
  // FastAPI's `detail`: a message string, or a list of validation errors.
  readonly detail: unknown
  readonly retryAfterSeconds: number | null

  constructor(status: number, detail: unknown, retryAfterSeconds: number | null) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) {
      return decodeURIComponent(rest.join('='))
    }
  }
  return null
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = { Accept: 'application/json' }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  // The backend rejects cookie-authenticated state changes without it.
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE)
    if (csrfToken) {
      headers[CSRF_HEADER] = csrfToken
    }
  }

  const url = new URL(`${API_BASE}${path}`, window.location.origin)
  const response = await fetch(url, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: 'same-origin',
    signal: options.signal,
  })

  if (!response.ok) {
    let detail: unknown = null
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail ?? null
    } catch {
      // Not every error has a JSON body (for example a proxy error page).
    }
    const retryAfter = response.headers.get('Retry-After')
    throw new ApiError(response.status, detail, retryAfter === null ? null : Number(retryAfter))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
