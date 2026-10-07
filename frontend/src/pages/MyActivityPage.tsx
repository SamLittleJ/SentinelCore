import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { SegmentedControl } from '@/components/SegmentedControl'
import { ActivityTable } from '@/features/account/ActivityTable'
import { ALERT_SEVERITIES, type ActivityFilters } from '@/features/account/api'
import { useMyActivity } from '@/features/account/hooks'

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

  const options: { value: FilterName; label: string }[] = [
    { value: 'all', label: t('activity.filterAll') },
    { value: 'alerts', label: t('activity.filterAlerts') },
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{t('nav.myActivity')}</h1>
        <p className="max-w-prose text-muted-foreground">{t('activity.subtitle')}</p>
      </header>

      <SegmentedControl
        label={t('activity.filterLabel')}
        options={options}
        value={filter}
        onChange={(name) => setSearchParams(name === 'all' ? {} : { filter: name })}
      />

      <PagedResults
        query={activity}
        empty={filter === 'alerts' ? t('activity.emptyAlerts') : t('activity.empty')}
      >
        {(events) => <ActivityTable events={events} />}
      </PagedResults>
    </div>
  )
}
