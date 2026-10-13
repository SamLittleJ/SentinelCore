import { useEffect, useId } from 'react'
import { useTranslation } from 'react-i18next'

import { useOrganizations } from './hooks'
import { useOrganizationView } from './organization-view'

/** The platform owner's choice of organization for every organization page:
 * all of them, or one. Suspended ones stay listed, since their records do. */
export function OrganizationPicker() {
  const { t } = useTranslation()
  const id = useId()
  const { organizationId, choose } = useOrganizationView()
  const organizations = useOrganizations(true)
  const known =
    organizationId === null ||
    organizations.data === undefined ||
    organizations.data.some((organization) => organization.id === organizationId)

  // An address naming no organization falls back to all of them.
  useEffect(() => {
    if (!known) choose(null)
  }, [known, choose])

  return (
    <div className="flex flex-col gap-1.5 px-1">
      <label htmlFor={id} className="label-mono text-muted-foreground">
        {t('organizationView.label')}
      </label>
      <select
        id={id}
        value={known && organizationId !== null ? organizationId : ''}
        onChange={(event) => choose(event.target.value === '' ? null : Number(event.target.value))}
        className="h-9 w-full rounded-md border border-sidebar-border bg-background/40 px-2.5 text-sm text-sidebar-foreground outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      >
        <option value="">{t('organizationView.all')}</option>
        {organizations.data?.map((organization) => (
          <option key={organization.id} value={organization.id}>
            {organization.suspended_at === null
              ? organization.name
              : t('organizationView.suspended', { name: organization.name })}
          </option>
        ))}
      </select>
    </div>
  )
}
