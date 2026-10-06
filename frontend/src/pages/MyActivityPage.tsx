import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ActivityTable } from '@/features/account/ActivityTable'
import { ALERT_SEVERITIES, type ActivityFilters } from '@/features/account/api'
import { useMyActivity } from '@/features/account/hooks'
import { cn } from '@/lib/utils'

const FILTERS = {
  all: {},
  alerts: { severity: ALERT_SEVERITIES },
} satisfies Record<string, ActivityFilters>

type FilterName = keyof typeof FILTERS

function isFilterName(value: string | null): value is FilterName {
  return value !== null && Object.hasOwn(FILTERS, value)
}

export function MyActivityPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('filter')
  const filter: FilterName = isFilterName(requested) ? requested : 'all'
  const activity = useMyActivity(FILTERS[filter])

  const events = activity.data?.pages.flatMap((page) => page.items) ?? []

  const options: { name: FilterName; label: string }[] = [
    { name: 'all', label: t('activity.filterAll') },
    { name: 'alerts', label: t('activity.filterAlerts') },
  ]

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{t('nav.myActivity')}</h1>
        <p className="max-w-prose text-muted-foreground">{t('activity.subtitle')}</p>
      </header>

      <div
        role="group"
        aria-label={t('activity.filterLabel')}
        className="inline-flex w-fit gap-1 rounded-lg border bg-card p-1"
      >
        {options.map((option) => (
          <button
            key={option.name}
            type="button"
            aria-pressed={filter === option.name}
            onClick={() => setSearchParams(option.name === 'all' ? {} : { filter: option.name })}
            className={cn(
              'rounded-md px-3 py-1 text-sm transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              filter === option.name
                ? 'bg-brand-tint font-medium text-brand'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {activity.isPending ? (
        <div className="flex flex-col gap-2" role="status" aria-label={t('app.loading')}>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : activity.isError && events.length === 0 ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
          <p className="text-muted-foreground">{t('errors.loadFailedBody')}</p>
          <Button variant="outline" size="sm" onClick={() => void activity.refetch()}>
            {t('errors.retry')}
          </Button>
        </div>
      ) : events.length === 0 ? (
        <p className="rounded-lg border bg-card px-4 py-6 text-muted-foreground">
          {filter === 'alerts' ? t('activity.emptyAlerts') : t('activity.empty')}
        </p>
      ) : (
        <div className="flex flex-col items-start gap-3">
          <ActivityTable events={events} />
          {activity.hasNextPage ? (
            <Button
              variant="outline"
              disabled={activity.isFetchingNextPage}
              onClick={() => void activity.fetchNextPage()}
            >
              {activity.isFetchingNextPage ? t('activity.loadingMore') : t('activity.loadMore')}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">{t('activity.end')}</p>
          )}
          {activity.isFetchNextPageError && (
            <p role="alert" className="text-sev-incident">
              {t('errors.loadFailedBody')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
