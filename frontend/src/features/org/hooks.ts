import { useInfiniteQuery } from '@tanstack/react-query'

import type { Page, SecurityEventType } from '@/features/account/api'

import {
  type AuditEventType,
  type AuditLog,
  fetchAuditLogs,
  fetchSecurityEvents,
  type LogQuery,
  type SecurityEvent,
} from './api'
import { type LogFilters, searchQuery, sinceFor } from './filters'

// Everything under this key is organization data, not the reader's own.
const orgKey = ['org'] as const
export const securityEventsKey = [...orgKey, 'security-events'] as const
export const auditLogsKey = [...orgKey, 'audit-logs'] as const

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
