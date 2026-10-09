import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { ActivityEvent, Page, Session } from '@/features/account/api'
import type { Role, User } from '@/features/auth/api'
import type { ApiKey, AuditLog, SecurityEvent, SecuritySummary } from '@/features/org/api'

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

export function makeSecurityEvent(overrides: Partial<SecurityEvent> = {}): SecurityEvent {
  return {
    id: 500,
    event_type: 'login_failed',
    severity: 'warn',
    user_id: null,
    target_user_id: null,
    email: 'mihai.pop@example.com',
    ip_address: '203.0.113.9',
    source: 'backend',
    message: 'Failed login attempt for email: mihai.pop@example.com',
    created_at: '2026-10-06T08:15:00Z',
    occurred_at: null,
    mitre_technique: null,
    ...overrides,
  }
}

export function makeAuditLog(overrides: Partial<AuditLog> = {}): AuditLog {
  return {
    id: 900,
    event_type: 'users_viewed',
    user_id: 3,
    target_user_id: null,
    email: 'ioana.sec@example.com',
    ip_address: '192.0.2.44',
    message: 'Listed users with no filters',
    created_at: '2026-10-06T09:00:00Z',
    ...overrides,
  }
}

export function makeApiKey(overrides: Partial<ApiKey> = {}): ApiKey {
  return {
    id: 3,
    prefix: 'a1b2c3d4',
    name: 'Corporate VPN',
    source: 'vpn',
    created_by_id: 1,
    created_at: '2026-09-01T10:00:00Z',
    expires_at: new Date(Date.now() + 30 * 24 * 3600_000).toISOString(),
    revoked_at: null,
    last_used_at: null,
    ...overrides,
  }
}

export function makeSummary(overrides: Partial<SecuritySummary> = {}): SecuritySummary {
  return {
    generated_at: new Date().toISOString(),
    last_24h: { info: 0, warn: 0, incident: 0 },
    last_7d: { info: 0, warn: 0, incident: 0 },
    failed_logins_24h: 0,
    locked_logins: 0,
    top_failed_login_sources: [],
    users_total: 1,
    users_inactive: 0,
    accounts_locked: 0,
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
  http.get('/api/security/events', () => HttpResponse.json(page([]))),
  http.get('/api/security/summary', () => HttpResponse.json(makeSummary())),
  http.get('/api/admin/audit-logs', () => HttpResponse.json(page([]))),
  http.get('/api/admin/users', () => HttpResponse.json(page([]))),
  http.get('/api/admin/users/:userId', ({ params }) =>
    HttpResponse.json(makeUser('user', { id: Number(params.userId) })),
  ),
  http.get('/api/admin/users/:userId/activity', () => HttpResponse.json(page([]))),
  http.get('/api/admin/api-keys', () => HttpResponse.json([])),
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
