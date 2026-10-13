import { useTranslation } from 'react-i18next'

import { useCurrentUser } from '@/features/auth/hooks'

import { useOrganizations } from './hooks'
import type { LogColumn } from './LogTable'
import { useViewedOrganization } from './organization-view'

/** Names a record's organization, or the platform for records of none. Null
 * when the reader sees one organization only, where the column would repeat
 * the same name on every row: members always, the owner after choosing one. */
export function useOrganizationName(): ((organizationId: number | null) => string) | null {
  const { t } = useTranslation()
  const { data: user } = useCurrentUser()
  const viewed = useViewedOrganization()
  const showsAll = user?.role === 'owner' && viewed === null
  const organizations = useOrganizations(showsAll)

  if (!showsAll) return null
  return (organizationId) => {
    if (organizationId === null) return t('organizations.platform')
    const found = organizations.data?.find((organization) => organization.id === organizationId)
    return found?.name ?? `#${organizationId}`
  }
}

/** The organization column of a log, when the reader sees several. */
export function useOrganizationColumn<Item extends { organization_id: number | null }>(): LogColumn<Item>[] {
  const { t } = useTranslation()
  const nameOf = useOrganizationName()
  if (nameOf === null) return []
  return [
    {
      header: t('organizations.column'),
      cell: (item) => nameOf(item.organization_id),
      className: 'max-w-40 truncate text-xs',
    },
  ]
}
