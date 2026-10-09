import type { ApiKey } from './api'

export type KeyState = 'active' | 'expired' | 'revoked'

/** Whether `key` still lets a system send events at `now`, as the API
 * decides it: a revoked key stays revoked, whatever its expiry. */
export function keyState(key: ApiKey, now = Date.now()): KeyState {
  if (key.revoked_at !== null) return 'revoked'
  return Date.parse(key.expires_at) > now ? 'active' : 'expired'
}

// The API's bounds for a new key, after trimming. It still decides.
export const KEY_NAME_MIN = 3
export const KEY_NAME_MAX = 100
export const SOURCE_MAX = 50
// The application's own events; an ingested event may never pass for one.
const RESERVED_SOURCES: ReadonlySet<string> = new Set(['backend', 'detection'])
const SOURCE_PATTERN = /^[a-z0-9][a-z0-9_.-]{1,49}$/

export type SourceProblem = 'format' | 'reserved'

/** What is wrong with `source`, once trimmed and lowercased as the API
 * stores it, or null when the API would accept it. */
export function sourceProblem(source: string): SourceProblem | null {
  const normalized = source.trim().toLowerCase()
  if (!SOURCE_PATTERN.test(normalized)) return 'format'
  return RESERVED_SOURCES.has(normalized) ? 'reserved' : null
}

export function validKeyName(name: string): boolean {
  const length = name.trim().length
  return length >= KEY_NAME_MIN && length <= KEY_NAME_MAX
}
