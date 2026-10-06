import { useTranslation } from 'react-i18next'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCurrentUser } from '@/features/auth/hooks'

export function MyOverviewPage() {
  const { t, i18n } = useTranslation()
  const { data: user } = useCurrentUser()

  if (user === undefined) {
    return null
  }

  const memberSince = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'long' }).format(
    new Date(user.created_at),
  )

  const rows: { label: string; value: string; mono?: boolean }[] = [
    { label: t('overview.username'), value: user.username, mono: true },
    { label: t('overview.email'), value: user.email },
    { label: t('overview.role'), value: t(`roles.${user.role}`) },
    { label: t('overview.memberSince'), value: memberSince },
  ]

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="text-xl font-semibold text-balance">
        {t('overview.greeting', { name: user.username })}
      </h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t('overview.profile')}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-[max-content_1fr]">
            {rows.map((row) => (
              <div key={row.label} className="contents">
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd className={row.mono ? 'font-mono' : undefined}>{row.value}</dd>
              </div>
            ))}
            <dt className="text-muted-foreground">{t('overview.status')}</dt>
            <dd>
              <span className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium text-sev-ok bg-sev-ok-bg">
                <span aria-hidden className="size-1.5 rounded-full bg-sev-ok" />
                {t('overview.active')}
              </span>
            </dd>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}
