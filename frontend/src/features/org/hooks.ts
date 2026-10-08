import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Page, SecurityEventType } from '@/features/account/api'
import type { User } from '@/features/auth/api'

import {
  type AuditEventType,
  type AuditLog,
  fetchAuditLogs,
  fetchSecurityEvents,
  fetchUser,
  fetchUserActivity,
  fetchUsers,
  type LogQuery,
  revokeUserSessions,
  type SecurityEvent,
} from './api'
import { type LogFilters, searchQuery, sinceFor } from './filters'
import type { UserFilters } from './user-filters'

// Everything under this key is organization data, not the reader's own.
const orgKey = ['org'] as const
export const securityEventsKey = [...orgKey, 'security-events'] as const
export const auditLogsKey = [...orgKey, 'audit-logs'] as const
const usersKey = [...orgKey, 'users'] as const
export const userListKey = [...usersKey, 'list'] as const
const userKey = (userId: number) => [...usersKey, 'detail', userId] as const
const userActivityKey = (userId: number) => [...usersKey, 'activity', userId] as const

interface Cursor {
  beforeId: number
  since: string | undefined
}

type AnchoredPage<Item> = Page<Item> & { since: string | undefined }

function useLogPages<Item, Type extends string>(
  key: readonly unknown[],
  filters: LogFilters<Type>,
  fetchPage: (query: LogQuery, signal: AbortSignal) => Promise<Page<Item>>,
) {
  return useInfiniteQuery({
    queryKey: [...key, filters],
    queryFn: async ({ pageParam, signal }): Promise<AnchoredPage<Item>> => {
      // The time window starts when the first page loads. Later pages keep
      // that start, so loading more never shifts the window.
      const since = pageParam ? pageParam.since : sinceFor(filters.range)
      const page = await fetchPage(
        {
          ...searchQuery(filters.search),
          userId: filters.userId,
          targetUserId: filters.targetUserId,
          since,
          beforeId: pageParam?.beforeId,
        },
        signal,
      )
      return { ...page, since }
    },
    initialPageParam: null as Cursor | null,
    getNextPageParam: (lastPage): Cursor | null =>
      lastPage.next_cursor === null
        ? null
        : { beforeId: lastPage.next_cursor, since: lastPage.since },
    // Every load is audited, so the log does not reload on its own when the
    // window regains focus; the page offers an explicit refresh.
    refetchOnWindowFocus: false,
  })
}

export function useSecurityEvents(filters: LogFilters<SecurityEventType>) {
  return useLogPages<SecurityEvent, SecurityEventType>(
    securityEventsKey,
    filters,
    (query, signal) =>
      fetchSecurityEvents(
        { ...query, eventType: filters.types, severity: filters.severities },
        signal,
      ),
  )
}

export function useAuditLogs(filters: LogFilters<AuditEventType>) {
  return useLogPages<AuditLog, AuditEventType>(auditLogsKey, filters, (query, signal) =>
    fetchAuditLogs({ ...query, eventType: filters.types }, signal),
  )
}

// Reading accounts is audited too, so these do not reload on window focus.

export function useUsers(filters: UserFilters) {
  return useInfiniteQuery({
    queryKey: [...userListKey, filters],
    queryFn: ({ pageParam, signal }) =>
      fetchUsers(
        { search: filters.search, roles: filters.roles, state: filters.state, beforeId: pageParam },
        signal,
      ),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    refetchOnWindowFocus: false,
  })
}

export function useUser(userId: number) {
  return useQuery({
    queryKey: userKey(userId),
    queryFn: ({ signal }) => fetchUser(userId, signal),
    refetchOnWindowFocus: false,
  })
}

export function useUserActivity(userId: number) {
  return useInfiniteQuery({
    queryKey: userActivityKey(userId),
    queryFn: ({ pageParam, signal }) => fetchUserActivity(userId, pageParam, signal),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    refetchOnWindowFocus: false,
  })
}

/** Marks stale what an action on the account adds to: its history, the
 * user list and both logs. A failed action may mean the account changed
 * meanwhile, so it is read again too. */
function useAfterAccountAction(userId: number) {
  const queryClient = useQueryClient()
  return (failed: boolean) => {
    const keys: (readonly unknown[])[] = [userActivityKey(userId), userListKey, securityEventsKey, auditLogsKey]
    if (failed) keys.push(userKey(userId))
    for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey })
  }
}

/** An action the API answers with the changed account. */
export function useAccountChange<Variables>(
  userId: number,
  change: (variables: Variables) => Promise<User>,
) {
  const queryClient = useQueryClient()
  const afterAction = useAfterAccountAction(userId)
  return useMutation({
    mutationFn: change,
    onSuccess: (user) => queryClient.setQueryData(userKey(userId), user),
    onSettled: (_user, error) => afterAction(error !== null),
  })
}

export function useRevokeUserSessions(userId: number) {
  const afterAction = useAfterAccountAction(userId)
  return useMutation({
    mutationFn: (reason: string) => revokeUserSessions(userId, reason),
    onSettled: (_result, error) => afterAction(error !== null),
  })
}
