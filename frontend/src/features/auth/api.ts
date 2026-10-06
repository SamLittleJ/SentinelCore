import { apiRequest } from '@/lib/api'

export const ROLES = ['user', 'admin', 'security_analyst', 'owner'] as const
export type Role = (typeof ROLES)[number]

export interface User {
  id: number
  username: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

// Roles that may use the organization perspective, as enforced by the API.
const ORGANIZATION_ROLES: ReadonlySet<Role> = new Set(['admin', 'owner', 'security_analyst'])

export function canViewOrganization(user: User): boolean {
  return ORGANIZATION_ROLES.has(user.role)
}

export function fetchCurrentUser(signal?: AbortSignal): Promise<User> {
  return apiRequest<User>('/users/me', { signal })
}

// Browser login: the backend answers 204 and sets the httpOnly session cookie.
export function logIn(email: string, password: string): Promise<void> {
  return apiRequest<void>('/auth/session', {
    method: 'POST',
    body: { email, password },
  })
}

export function logOut(): Promise<void> {
  return apiRequest<void>('/auth/logout', { method: 'POST' })
}
