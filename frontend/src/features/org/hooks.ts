import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Page, SecurityEventType } from '@/features/account/api'
import type { User } from '@/features/auth/api'

import {
  type AuditEventType,
  type AuditLog,
  createApiKey,
  createInvitation,
  fetchApiKeys,
  fetchAuditLogs,
  fetchInvitations,
  fetchOrganizations,
  fetchSecurityEvents,
  fetchSecuritySummary,
  fetchUser,
  fetchUserActivity,
  fetchUsers,
  type LogQuery,
  createOrganization,
  reactivateOrganization,
  renameOrganization,
  revokeApiKey,
  revokeInvitation,
  revokeUserSessions,
  type SecurityEvent,
  suspendOrganization,
} from './api'
import { type LogFilters, searchQuery, sinceFor, type TimeRange } from './filters'
import { useViewedOrganization } from './organization-view'
import type { UserFilters } from './user-filters'

// Everything under this key is organization data, not the reader's own.
const orgKey = ['org'] as const
export const securityEventsKey = [...orgKey, 'security-events'] as const
export const auditLogsKey = [...orgKey, 'audit-logs'] as const
const usersKey = [...orgKey, 'users'] as const
export const userListKey = [...usersKey, 'list'] as const
const userKey = (userId: number) => [...usersKey, 'detail', userId] as const
const userActivityKey = (userId: number) => [...usersKey, 'activity', userId] as const
export const securitySummaryKey = [...orgKey, 'security-summary'] as const
export const apiKeysKey = [...orgKey, 'api-keys'] as const
export const invitationsKey = [...orgKey, 'invitations'] as const
export const organizationsKey = [...orgKey, 'organizations'] as const
// Under the events key, so whatever refreshes the event log refreshes it too.
export const recentIncidentsKey = [...securityEventsKey, 'recent-incidents'] as const

// How many incidents the overview lists, and how far back it looks.
export const RECENT_INCIDENTS = 5
export const RECENT_INCIDENTS_RANGE = '7d' satisfies TimeRange

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
  const organizationId = useViewedOrganization()
  return useInfiniteQuery({
    queryKey: [...key, organizationId, filters],
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
          organizationId,
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

/** The counts behind the organization overview. They are not audited, but
 * they reload only with the incidents beside them, so the two never disagree. */
export function useSecuritySummary() {
  const organizationId = useViewedOrganization()
  return useQuery({
    queryKey: [...securitySummaryKey, organizationId],
    queryFn: ({ signal }) => fetchSecuritySummary(organizationId, signal),
    refetchOnWindowFocus: false,
  })
}

/** The latest incidents for the overview. Reading them is audited, like any
 * read of the event log. */
export function useRecentIncidents() {
  const organizationId = useViewedOrganization()
  return useQuery({
    queryKey: [...recentIncidentsKey, organizationId],
    queryFn: ({ signal }) =>
      fetchSecurityEvents(
        {
          severity: ['incident'],
          since: sinceFor(RECENT_INCIDENTS_RANGE),
          limit: RECENT_INCIDENTS,
          organizationId,
        },
        signal,
      ),
    refetchOnWindowFocus: false,
  })
}

// Reading accounts is audited too, so these do not reload on window focus.

export function useUsers(filters: UserFilters) {
  const organizationId = useViewedOrganization()
  return useInfiniteQuery({
    queryKey: [...userListKey, organizationId, filters],
    queryFn: ({ pageParam, signal }) =>
      fetchUsers(
        {
          search: filters.search,
          roles: filters.roles,
          state: filters.state,
          beforeId: pageParam,
          organizationId,
        },
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

/** Every API key. Listing them is audited, so they reload only on request. */
export function useApiKeys() {
  const organizationId = useViewedOrganization()
  return useQuery({
    queryKey: [...apiKeysKey, organizationId],
    queryFn: ({ signal }) => fetchApiKeys(organizationId, signal),
    refetchOnWindowFocus: false,
  })
}

/** Issuing or revoking a key changes the list and adds to both logs. */
function useAfterKeyChange() {
  const queryClient = useQueryClient()
  return () => {
    for (const queryKey of [apiKeysKey, securityEventsKey, auditLogsKey]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }
}

/** Issues a key. The answer holds the full key, which must not outlive the
 * moment it is shown: the page keeps it in its own state and resets this
 * mutation, and `gcTime: 0` then drops it from the mutation cache at once. */
export function useCreateApiKey() {
  const afterChange = useAfterKeyChange()
  return useMutation({ mutationFn: createApiKey, gcTime: 0, onSettled: afterChange })
}

export function useRevokeApiKey() {
  const afterChange = useAfterKeyChange()
  return useMutation({ mutationFn: revokeApiKey, onSettled: afterChange })
}

/** Every invitation. Listing them is audited, so they reload only on request. */
export function useInvitations() {
  const organizationId = useViewedOrganization()
  return useQuery({
    queryKey: [...invitationsKey, organizationId],
    queryFn: ({ signal }) => fetchInvitations(organizationId, signal),
    refetchOnWindowFocus: false,
  })
}

/** Inviting or revoking changes the list and adds to both logs. */
function useAfterInvitationChange() {
  const queryClient = useQueryClient()
  return () => {
    for (const queryKey of [invitationsKey, securityEventsKey, auditLogsKey]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }
}

/** Issues an invitation. Its token, like a new API key, must not outlive the
 * moment the link is shown: the page keeps it in its own state and resets
 * this mutation, and `gcTime: 0` then drops it from the mutation cache. */
export function useCreateInvitation() {
  const afterChange = useAfterInvitationChange()
  return useMutation({ mutationFn: createInvitation, gcTime: 0, onSettled: afterChange })
}

export function useRevokeInvitation() {
  const afterChange = useAfterInvitationChange()
  return useMutation({ mutationFn: revokeInvitation, onSettled: afterChange })
}

/** The platform's organizations, for the owner's picker, forms and columns.
 * Listing them is audited, so they load once and then only after a change or
 * on request, not each time another part of the page asks for them. */
export function useOrganizations(enabled: boolean) {
  return useQuery({
    queryKey: organizationsKey,
    queryFn: ({ signal }) => fetchOrganizations(signal),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

/** A change to an organization shows in its list, in both logs, and in the
 * summary; suspending one also closes its members' sessions. */
function useAfterOrganizationChange() {
  const queryClient = useQueryClient()
  return () => {
    for (const queryKey of [organizationsKey, securityEventsKey, auditLogsKey, securitySummaryKey]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }
}

export function useCreateOrganization() {
  const afterChange = useAfterOrganizationChange()
  return useMutation({ mutationFn: createOrganization, onSettled: afterChange })
}

export function useRenameOrganization() {
  const afterChange = useAfterOrganizationChange()
  return useMutation({ mutationFn: renameOrganization, onSettled: afterChange })
}

export function useSuspendOrganization() {
  const afterChange = useAfterOrganizationChange()
  return useMutation({ mutationFn: suspendOrganization, onSettled: afterChange })
}

export function useReactivateOrganization() {
  const afterChange = useAfterOrganizationChange()
  return useMutation({ mutationFn: reactivateOrganization, onSettled: afterChange })
}
