import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { useOrganizations } from './hooks'
import { useOrganizationView } from './organization-view'

/** The platform owner's choice of organization for every organization page:
 * all of them, or one. Suspended ones stay listed, since their records do. */
export function OrganizationPicker() {
  const { t } = useTranslation()
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
    <select
      aria-label={t('organizationView.label')}
      value={known && organizationId !== null ? organizationId : ''}
      onChange={(event) => choose(event.target.value === '' ? null : Number(event.target.value))}
      className="h-9 max-w-56 rounded-md border border-input bg-background px-2.5 text-sm text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
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
  )
}
