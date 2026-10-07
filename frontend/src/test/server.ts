import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { ActivityEvent, Page, Session } from '@/features/account/api'
import type { Role, User } from '@/features/auth/api'

export function makeUser(role: Role = 'user', overrides: Partial<User> = {}): User {
  return {
    id: 7,
    username: 'elena.radu',
    email: 'elena.radu@example.com',
    role,
    is_active: true,
    locked_until: null,
    created_at: '2026-03-14T09:30:00Z',
    updated_at: '2026-10-01T12:00:00Z',
    ...overrides,
  }
}

export function makeSession(overrides: Partial<Session> = {}): Session {
  const now = Date.now()
  return {
    id: '5b0c6a8e-0f7e-4c3a-9a51-2f1d9d6a1c01',
    created_at: new Date(now - 5 * 60_000).toISOString(),
    expires_at: new Date(now + 25 * 60_000).toISOString(),
    ip_address: '192.0.2.10',
    user_agent: 'Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0',
    current: true,
    ...overrides,
  }
}

export function makeEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: 100,
    event_type: 'login_success',
    severity: 'info',
    ip_address: '192.0.2.10',
    created_at: '2026-10-06T08:15:00Z',
    as_target: false,
    ...overrides,
  }
}

export function page<T>(items: T[], nextCursor: number | null = null): Page<T> {
  return { items, next_cursor: nextCursor }
}

// Every page can render: tests override these with the data they need.
export const server = setupServer(
  http.get('/api/users/me/sessions', () => HttpResponse.json([makeSession()])),
  http.get('/api/users/me/activity', () => HttpResponse.json(page([]))),
)

/** The API answers as if `user` is signed in (or nobody, for null). */
export function signedInAs(user: User | null) {
  server.use(
    http.get('/api/users/me', () =>
      user === null
        ? HttpResponse.json({ detail: 'Could not validate credentials' }, { status: 401 })
        : HttpResponse.json(user),
    ),
  )
}
