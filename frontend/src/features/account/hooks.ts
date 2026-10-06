import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  type ActivityFilters,
  fetchMyActivity,
  fetchMySessions,
  revokeOtherSessions,
  revokeSession,
} from './api'

// Everything under this key belongs to the signed-in user's own account.
const accountKey = ['account'] as const
const sessionsKey = [...accountKey, 'sessions'] as const
const activityKey = [...accountKey, 'activity'] as const

export function useMySessions() {
  return useQuery({
    queryKey: sessionsKey,
    queryFn: ({ signal }) => fetchMySessions(signal),
  })
}

export function useRevokeSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: revokeSession,
    // Also after a 404: the session was already gone, so the list is stale.
    onSettled: () => queryClient.invalidateQueries({ queryKey: sessionsKey }),
  })
}

export function useRevokeOtherSessions() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: revokeOtherSessions,
    onSettled: () => queryClient.invalidateQueries({ queryKey: sessionsKey }),
  })
}

/** Activity pages, loaded on demand with the cursor of the previous page. */
export function useMyActivity(filters: ActivityFilters) {
  return useInfiniteQuery({
    queryKey: [...activityKey, filters],
    queryFn: ({ pageParam, signal }) => fetchMyActivity(filters, pageParam, signal),
    initialPageParam: null as number | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  })
}

/** The first page only, for summaries. */
export function useMyActivitySummary(filters: ActivityFilters) {
  return useQuery({
    queryKey: [...activityKey, 'summary', filters],
    queryFn: ({ signal }) => fetchMyActivity(filters, null, signal),
  })
}
