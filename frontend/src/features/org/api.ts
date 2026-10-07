import type { Page, SecurityEventType, Severity } from '@/features/account/api'
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
