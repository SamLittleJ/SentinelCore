import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { StatusPage } from '@/components/StatusPage'
import { Button } from '@/components/ui/button'

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
