import { useEffect, useId } from 'react'
import { useTranslation } from 'react-i18next'

import { useOrganizations } from '@/features/org/hooks'

/** The organization something new is made in, chosen by the platform owner
 * among those not suspended. With only one, it is chosen already. */
export function OrganizationField({
  value,
  onChange,
}: {
  value: number | null
  onChange: (organizationId: number | null) => void
}) {
  const { t } = useTranslation()
  const id = useId()
  const helpId = useId()
  const organizations = useOrganizations(true)
  const open = organizations.data?.filter((item) => item.suspended_at === null) ?? []
  const only = open.length === 1 ? open[0].id : null

  useEffect(() => {
    if (value === null && only !== null) onChange(only)
  }, [only, value, onChange])

  const help = organizations.isPending
    ? t('app.loading')
    : organizations.isError
      ? t('organizationField.failed')
      : open.length === 0
        ? t('organizationField.none')
        : t('organizationField.help')

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {t('organizationField.label')}
      </label>
      <select
        id={id}
        value={value ?? ''}
        onChange={(event) =>
          onChange(event.target.value === '' ? null : Number(event.target.value))
        }
        disabled={open.length === 0}
        aria-describedby={helpId}
        className="h-9 w-full max-w-md rounded-md border border-input bg-background px-3 py-1 text-base shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
      >
        <option value="">{t('organizationField.choose')}</option>
        {open.map((organization) => (
          <option key={organization.id} value={organization.id}>
            {organization.name} ({organization.slug})
          </option>
        ))}
      </select>
      <p
        id={helpId}
        role={organizations.isError ? 'alert' : undefined}
        className="text-xs text-muted-foreground"
      >
        {help}
      </p>
    </div>
  )
}
