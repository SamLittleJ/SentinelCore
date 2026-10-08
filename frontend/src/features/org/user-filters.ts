import { ROLES, type Role } from '@/features/auth/api'

import { ACCOUNT_STATES, type AccountState } from './api'

/** What the user list filters by, as kept in the address. */
export interface UserFilters {
  // A substring of the username or email.
  search: string
  roles: Role[]
  state?: AccountState
}

const PARAMS = { search: 'q', role: 'role', state: 'state' } as const

function isOneOf<T extends string>(values: readonly T[], value: string): value is T {
  return (values as readonly string[]).includes(value)
}

/** Reads filters from the address, ignoring values that are not valid. */
export function readUserFilters(params: URLSearchParams): UserFilters {
  const state = params.get(PARAMS.state) ?? ''
  return {
    search: params.get(PARAMS.search)?.trim() ?? '',
    roles: params.getAll(PARAMS.role).filter((role) => isOneOf(ROLES, role)),
    state: isOneOf(ACCOUNT_STATES, state) ? state : undefined,
  }
}

export function writeUserFilters(filters: UserFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.search) params.set(PARAMS.search, filters.search)
  for (const role of filters.roles) params.append(PARAMS.role, role)
  if (filters.state) params.set(PARAMS.state, filters.state)
  return params
}

export function hasUserFilters(filters: UserFilters): boolean {
  return filters.search !== '' || filters.roles.length > 0 || filters.state !== undefined
}

/** Where an account's page goes back to: the list as it was filtered. */
export interface UserPageState {
  from: string
}
