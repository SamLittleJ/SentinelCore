import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Role, User } from '@/features/auth/api'

export function makeUser(role: Role = 'user', overrides: Partial<User> = {}): User {
  return {
    id: 7,
    username: 'elena.radu',
    email: 'elena.radu@example.com',
    role,
    is_active: true,
    created_at: '2026-03-14T09:30:00Z',
    updated_at: '2026-10-01T12:00:00Z',
    ...overrides,
  }
}

export const server = setupServer()

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
