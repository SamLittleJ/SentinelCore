import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/** The parts of a TanStack infinite query over cursor pages that this uses. */
export interface PagedQuery<Item> {
  data?: { pages: { items: Item[] }[] }
  isPending: boolean
  isError: boolean
  error: Error | null
  refetch: () => unknown
  hasNextPage: boolean
  isFetchingNextPage: boolean
  isFetchNextPageError: boolean
  fetchNextPage: () => unknown
}

interface PagedResultsProps<Item> {
  query: PagedQuery<Item>
  empty: ReactNode
  // The message for a failed first load; defaults to the generic one.
  errorMessage?: (error: Error | null) => string | undefined
  children: (items: Item[]) => ReactNode
}

/** Loading, error and empty states, the items, and "load more" for a
 * newest-first list read with a cursor. */
export function PagedResults<Item>({ query, empty, errorMessage, children }: PagedResultsProps<Item>) {
  const { t } = useTranslation()
  const items = query.data?.pages.flatMap((page) => page.items) ?? []

  if (query.isPending) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label={t('app.loading')}>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (query.isError && items.length === 0) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
        <p className="text-muted-foreground">
          {errorMessage?.(query.error) ?? t('errors.loadFailedBody')}
        </p>
        <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
          {t('errors.retry')}
        </Button>
      </div>
    )
  }

  if (items.length === 0) {
    return <p className="rounded-lg border bg-card px-4 py-6 text-muted-foreground">{empty}</p>
  }

  return (
    <div className="flex flex-col items-start gap-3">
      {children(items)}
      {query.hasNextPage ? (
        <Button
          variant="outline"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {query.isFetchingNextPage ? t('paging.loadingMore') : t('paging.loadMore')}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">{t('paging.end')}</p>
      )}
      {query.isFetchNextPageError && (
        <p role="alert" className="text-sev-incident">
          {t('errors.loadFailedBody')}
        </p>
      )}
    </div>
  )
}
