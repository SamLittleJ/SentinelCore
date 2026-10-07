import { SEVERITIES, type Severity } from '@/features/account/api'

import type { LogQuery } from './api'

export const TIME_RANGES = ['1h', '24h', '7d', '30d', 'all'] as const
export type TimeRange = (typeof TIME_RANGES)[number]
export const DEFAULT_RANGE: TimeRange = '7d'

const HOUR = 60 * 60_000
const RANGE_MS: Record<Exclude<TimeRange, 'all'>, number> = {
  '1h': HOUR,
  '24h': 24 * HOUR,
  '7d': 7 * 24 * HOUR,
  '30d': 30 * 24 * HOUR,
}

/** What a log page filters by, as kept in the address. */
export interface LogFilters<Type extends string> {
  range: TimeRange
  types: Type[]
  // Only the security events log has severities.
  severities: Severity[]
  // An exact email or IP address.
  search: string
  userId?: number
  targetUserId?: number
}

// Short names, since the address is shared as a link.
const PARAMS = {
  range: 'range',
  type: 'type',
  severity: 'severity',
  search: 'q',
  user: 'user',
  target: 'target',
} as const

function isOneOf<T extends string>(values: readonly T[], value: string): value is T {
  return (values as readonly string[]).includes(value)
}

function positiveInt(value: string | null): number | undefined {
  return value !== null && /^[1-9]\d*$/.test(value) ? Number(value) : undefined
}

/** Reads filters from the address, ignoring values that are not valid. */
export function readLogFilters<Type extends string>(
  params: URLSearchParams,
  knownTypes: readonly Type[],
): LogFilters<Type> {
  const range = params.get(PARAMS.range) ?? ''
  return {
    range: isOneOf(TIME_RANGES, range) ? range : DEFAULT_RANGE,
    types: params.getAll(PARAMS.type).filter((type) => isOneOf(knownTypes, type)),
    severities: params.getAll(PARAMS.severity).filter((value) => isOneOf(SEVERITIES, value)),
    search: params.get(PARAMS.search)?.trim() ?? '',
    userId: positiveInt(params.get(PARAMS.user)),
    targetUserId: positiveInt(params.get(PARAMS.target)),
  }
}

/** The address form of `filters`, leaving defaults out. */
export function writeLogFilters(filters: LogFilters<string>): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.range !== DEFAULT_RANGE) params.set(PARAMS.range, filters.range)
  for (const type of filters.types) params.append(PARAMS.type, type)
  for (const severity of filters.severities) params.append(PARAMS.severity, severity)
  if (filters.search) params.set(PARAMS.search, filters.search)
  if (filters.userId !== undefined) params.set(PARAMS.user, String(filters.userId))
  if (filters.targetUserId !== undefined) params.set(PARAMS.target, String(filters.targetUserId))
  return params
}

/** The start of `range` measured back from `now`, or undefined for all time. */
export function sinceFor(range: TimeRange, now = Date.now()): string | undefined {
  return range === 'all' ? undefined : new Date(now - RANGE_MS[range]).toISOString()
}

const IPV4 = /^\d{1,3}(\.\d{1,3}){3}$/

/** The API filters email and IP separately; an address with ':' is IPv6. */
export function searchQuery(search: string): Pick<LogQuery, 'email' | 'ipAddress'> {
  if (!search) return {}
  return IPV4.test(search) || search.includes(':') ? { ipAddress: search } : { email: search }
}

export function hasNarrowingFilters(filters: LogFilters<string>): boolean {
  return (
    filters.types.length > 0 ||
    filters.severities.length > 0 ||
    filters.search !== '' ||
    filters.userId !== undefined ||
    filters.targetUserId !== undefined
  )
}
