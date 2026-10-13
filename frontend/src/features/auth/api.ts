import { ApiError, apiRequest } from '@/lib/api'

export const ROLES = ['user', 'admin', 'security_analyst', 'owner'] as const
export type Role = (typeof ROLES)[number]

export interface User {
  id: number
  username: string
  email: string
  role: Role
  // Null for the platform owner, who belongs to no organization.
  organization_id: number | null
  is_active: boolean
  // Set while an operator's lock is in force or after it expired.
  locked_until: string | null
  created_at: string
  updated_at: string
}

/** The signed-in account, with the name of its organization. */
export interface CurrentUser extends User {
  organization: { id: number; name: string; slug: string } | null
}

// Roles that may use the organization perspective, as enforced by the API.
const ORGANIZATION_ROLES: ReadonlySet<Role> = new Set(['admin', 'owner', 'security_analyst'])

export function canViewOrganization(user: User): boolean {
  return ORGANIZATION_ROLES.has(user.role)
}

// The API answers 403 both for a deactivated account and for one an operator
// has locked; the detail tells them apart.
const ACCOUNT_LOCKED_DETAIL = 'Account temporarily locked'

export function isAccountLockedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403 && error.detail === ACCOUNT_LOCKED_DETAIL
}

export function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  return apiRequest<CurrentUser>('/users/me', { signal })
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

/** What an invitation offers, shown before its holder picks a username and
 * a password. */
export interface InvitationPreview {
  email: string
  role: Role
  expires_at: string
}

// The token travels in the body, never in the address, so it stays out of
// access logs. Every invalid token gets the same 404.
export function previewInvitation(token: string, signal?: AbortSignal): Promise<InvitationPreview> {
  return apiRequest<InvitationPreview>('/auth/invitations/preview', {
    method: 'POST',
    body: { token },
    signal,
  })
}

export interface InvitationAcceptance {
  token: string
  username: string
  password: string
}

/** Creates the invited account. It does not sign in: its owner signs in
 * next, as every time. */
export function acceptInvitation(acceptance: InvitationAcceptance): Promise<User> {
  return apiRequest<User>('/auth/invitations/accept', { method: 'POST', body: acceptance })
}

// The API's bounds for a new account. It still decides.
export const USERNAME_MIN = 3
export const USERNAME_MAX = 50
const USERNAME_PATTERN = /^[A-Za-z0-9_.-]+$/
export const PASSWORD_MIN = 12
export const PASSWORD_MAX = 128

export function validUsername(username: string): boolean {
  return (
    username.length >= USERNAME_MIN &&
    username.length <= USERNAME_MAX &&
    USERNAME_PATTERN.test(username)
  )
}

export function validNewPassword(password: string): boolean {
  // Counted as the API counts it, by code point: an emoji is one character.
  const length = Array.from(password).length
  return length >= PASSWORD_MIN && length <= PASSWORD_MAX
}
