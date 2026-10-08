import type { Page, SecurityEventType, Severity } from '@/features/account/api'
import type { Role, User } from '@/features/auth/api'
import { apiRequest } from '@/lib/api'

export const AUDIT_EVENT_TYPES = [
  'user_registered',
  'login_success',
  'login_failed',
  'admin_endpoint_accessed',
  'user_role_changed',
  'user_activated',
  'user_deactivated',
  'login_locked',
  'login_blocked',
  'audit_logs_viewed',
  'security_events_viewed',
  'session_revoked',
  'all_sessions_revoked',
  'other_sessions_revoked',
  'users_viewed',
  'account_locked',
  'account_unlocked',
] as const
export type AuditEventType = (typeof AUDIT_EVENT_TYPES)[number]

/** A security event with the operator details the personal view leaves out. */
export interface SecurityEvent {
  id: number
  event_type: SecurityEventType
  severity: Severity
  // The actor, or the account a failed login named.
  user_id: number | null
  // The account an operator acted on.
  target_user_id: number | null
  email: string | null
  ip_address: string | null
  source: string
  // Written by the backend for operators, in English.
  message: string
  created_at: string
}

export interface AuditLog {
  id: number
  event_type: AuditEventType
  user_id: number | null
  target_user_id: number | null
  email: string | null
  ip_address: string | null
  message: string | null
  created_at: string
}

/** Filters shared by both logs; the API matches email and IP exactly. */
export interface LogQuery {
  since?: string
  email?: string
  ipAddress?: string
  userId?: number
  targetUserId?: number
  beforeId?: number | null
  // Page size; the API defaults to 50.
  limit?: number
}

export interface SecurityEventQuery extends LogQuery {
  eventType?: readonly SecurityEventType[]
  severity?: readonly Severity[]
}

export interface AuditLogQuery extends LogQuery {
  eventType?: readonly AuditEventType[]
}

function logParams(query: LogQuery): URLSearchParams {
  const params = new URLSearchParams()
  if (query.since) params.set('since', query.since)
  if (query.email) params.set('email', query.email)
  if (query.ipAddress) params.set('ip_address', query.ipAddress)
  if (query.userId !== undefined) params.set('user_id', String(query.userId))
  if (query.targetUserId !== undefined) params.set('target_user_id', String(query.targetUserId))
  if (query.beforeId) params.set('before_id', String(query.beforeId))
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  return params
}

function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString()
  return query ? `${path}?${query}` : path
}

export function fetchSecurityEvents(
  query: SecurityEventQuery,
  signal?: AbortSignal,
): Promise<Page<SecurityEvent>> {
  const params = logParams(query)
  for (const type of query.eventType ?? []) params.append('event_type', type)
  for (const severity of query.severity ?? []) params.append('severity', severity)
  return apiRequest<Page<SecurityEvent>>(withQuery('/security/events', params), { signal })
}

export function fetchAuditLogs(
  query: AuditLogQuery,
  signal?: AbortSignal,
): Promise<Page<AuditLog>> {
  const params = logParams(query)
  for (const type of query.eventType ?? []) params.append('event_type', type)
  return apiRequest<Page<AuditLog>>(withQuery('/admin/audit-logs', params), { signal })
}

export interface SeverityCounts {
  info: number
  warn: number
  incident: number
}

/** Organization-wide aggregates, measured back from `generated_at` on the
 * database clock. Reading them is not audited: they hold counts, not records. */
export interface SecuritySummary {
  generated_at: string
  last_24h: SeverityCounts
  last_7d: SeverityCounts
  failed_logins_24h: number
  // Emails whose logins brute-force protection blocks right now.
  locked_logins: number
  // The addresses with the most failed logins in the last 24 hours, at most 5.
  top_failed_login_sources: { ip_address: string; failed_logins: number }[]
  users_total: number
  users_inactive: number
  // Accounts an operator has locked, whose lock has not expired.
  accounts_locked: number
}

export function fetchSecuritySummary(signal?: AbortSignal): Promise<SecuritySummary> {
  return apiRequest<SecuritySummary>('/security/summary', { signal })
}

// Account states the user list filters by. The API filters `is_active` and
// `locked` separately; "active" means neither deactivated nor locked.
export const ACCOUNT_STATES = ['active', 'locked', 'inactive'] as const
export type AccountState = (typeof ACCOUNT_STATES)[number]

export interface UserQuery {
  // A substring of the username or email.
  search?: string
  roles?: readonly Role[]
  state?: AccountState
  beforeId?: number | null
}

export function fetchUsers(query: UserQuery, signal?: AbortSignal): Promise<Page<User>> {
  const params = new URLSearchParams()
  if (query.search) params.set('q', query.search)
  for (const role of query.roles ?? []) params.append('role', role)
  if (query.state === 'active') {
    params.set('is_active', 'true')
    params.set('locked', 'false')
  } else if (query.state === 'locked') {
    params.set('locked', 'true')
  } else if (query.state === 'inactive') {
    params.set('is_active', 'false')
  }
  if (query.beforeId) params.set('before_id', String(query.beforeId))
  return apiRequest<Page<User>>(withQuery('/admin/users', params), { signal })
}

export function fetchUser(userId: number, signal?: AbortSignal): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}`, { signal })
}

/** The security events about one account, the set its owner sees, with the
 * operator details. */
export function fetchUserActivity(
  userId: number,
  beforeId: number | null,
  signal?: AbortSignal,
): Promise<Page<SecurityEvent>> {
  const params = new URLSearchParams()
  if (beforeId) params.set('before_id', String(beforeId))
  return apiRequest<Page<SecurityEvent>>(withQuery(`/admin/users/${userId}/activity`, params), {
    signal,
  })
}

// The roles an owner can assign; nobody is promoted to owner.
export const ASSIGNABLE_ROLES = ['user', 'security_analyst', 'admin'] as const satisfies readonly Role[]
export type AssignableRole = (typeof ASSIGNABLE_ROLES)[number]

export function changeUserRole(userId: number, role: AssignableRole): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}/role`, { method: 'PATCH', body: { role } })
}

export function changeUserStatus(userId: number, isActive: boolean): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}/status`, {
    method: 'PATCH',
    body: { is_active: isActive },
  })
}

/** Signs the user out everywhere; `reason` goes to the logs. */
export function revokeUserSessions(
  userId: number,
  reason: string,
): Promise<{ revoked_sessions: number }> {
  return apiRequest<{ revoked_sessions: number }>(`/admin/users/${userId}/revoke-sessions`, {
    method: 'POST',
    body: { reason },
  })
}

// The lock lengths offered, in hours; the API accepts 1 to 168.
export const LOCK_DURATIONS = [1, 24, 168] as const
export type LockDuration = (typeof LOCK_DURATIONS)[number]

/** Refuses the user's logins for `durationHours` and closes their sessions. */
export function lockUser(userId: number, durationHours: LockDuration, reason: string): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}/lock`, {
    method: 'POST',
    body: { duration_hours: durationHours, reason },
  })
}

export function unlockUser(userId: number): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}/unlock`, { method: 'POST' })
}
