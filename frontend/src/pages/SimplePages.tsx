import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { StatusPage } from '@/components/StatusPage'
import { Button } from '@/components/ui/button'

export function OrganizationOverviewPage() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-xl font-semibold">{t('orgOverview.title')}</h1>
      <p className="text-muted-foreground">{t('orgOverview.subtitle')}</p>
      <p className="text-muted-foreground">{t('placeholder.body')}</p>
    </div>
  )
}

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <StatusPage
      title={t('errors.notFoundTitle')}
      body={t('errors.notFoundBody')}
      action={
        <Button asChild variant="outline">
          <Link to="/me">{t('errors.backToAccount')}</Link>
        </Button>
      }
    />
  )
}
