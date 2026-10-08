import { apiRequest } from '@/lib/api'

export interface Session {
  id: string
  created_at: string
  expires_at: string
  ip_address: string | null
  user_agent: string | null
  // The session making the request, i.e. this browser.
  current: boolean
}

export const SECURITY_EVENT_TYPES = [
  'user_registered',
  'login_success',
  'login_failed',
  'admin_access',
  'user_role_changed',
  'user_activated',
  'user_deactivated',
  'brute_force_detected',
  'login_blocked',
  'user_sessions_revoked',
  'account_locked',
  'account_unlocked',
  'api_key_created',
  'api_key_revoked',
  // Alerts raised by the backend's detection rules.
  'password_spray_detected',
  'dormant_account_login',
  'privileged_role_granted',
] as const
export type SecurityEventType = (typeof SECURITY_EVENT_TYPES)[number]

// Actions an operator takes on an account, and the alerts they raise. They
// reach the affected account's activity too, marked `as_target`.
export const ACCOUNT_ACTION_TYPES = [
  'user_role_changed',
  'user_activated',
  'user_deactivated',
  'user_sessions_revoked',
  'account_locked',
  'account_unlocked',
  'privileged_role_granted',
] as const satisfies readonly SecurityEventType[]
export type AccountActionType = (typeof ACCOUNT_ACTION_TYPES)[number]

export function isAccountAction(type: SecurityEventType): type is AccountActionType {
  return (ACCOUNT_ACTION_TYPES as readonly SecurityEventType[]).includes(type)
}

export const SEVERITIES = ['info', 'warn', 'incident'] as const
export type Severity = (typeof SEVERITIES)[number]

// What the interface calls alerts: anything above informational.
export const ALERT_SEVERITIES: readonly Severity[] = ['warn', 'incident']

export interface ActivityEvent {
  id: number
  event_type: SecurityEventType
  severity: Severity
  // Null for actions taken on the account: the address is the operator's.
  ip_address: string | null
  created_at: string
  // True when someone else took this action on the reader's account.
  as_target: boolean
}

/** One page of results, newest first; `next_cursor` is the next `before_id`. */
export interface Page<T> {
  items: T[]
  next_cursor: number | null
}

export interface ActivityFilters {
  severity?: readonly Severity[]
  eventType?: readonly SecurityEventType[]
  since?: string
  limit?: number
}

export function fetchMySessions(signal?: AbortSignal): Promise<Session[]> {
  return apiRequest<Session[]>('/users/me/sessions', { signal })
}

export function revokeSession(sessionId: string): Promise<void> {
  return apiRequest<void>(`/users/me/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}

/** Signs out every other device; this browser stays signed in. */
export function revokeOtherSessions(): Promise<{ revoked_sessions: number }> {
  return apiRequest<{ revoked_sessions: number }>('/users/me/sessions', { method: 'DELETE' })
}

export function fetchMyActivity(
  filters: ActivityFilters,
  beforeId: number | null,
  signal?: AbortSignal,
): Promise<Page<ActivityEvent>> {
  const params = new URLSearchParams()
  for (const severity of filters.severity ?? []) {
    params.append('severity', severity)
  }
  for (const eventType of filters.eventType ?? []) {
    params.append('event_type', eventType)
  }
  if (filters.since) {
    params.set('since', filters.since)
  }
  if (filters.limit) {
    params.set('limit', String(filters.limit))
  }
  if (beforeId !== null) {
    params.set('before_id', String(beforeId))
  }
  const query = params.toString()
  return apiRequest<Page<ActivityEvent>>(`/users/me/activity${query ? `?${query}` : ''}`, {
    signal,
  })
}
