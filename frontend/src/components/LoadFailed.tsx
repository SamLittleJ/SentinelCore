import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'

/** A section that could not load, with a way to try again. */
export function LoadFailed({ onRetry }: { onRetry: () => unknown }) {
  const { t } = useTranslation()
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border px-4 py-4">
      <p className="text-muted-foreground">{t('errors.loadFailedBody')}</p>
      <Button variant="outline" size="sm" onClick={() => void onRetry()}>
        {t('errors.retry')}
      </Button>
    </div>
  )
}
