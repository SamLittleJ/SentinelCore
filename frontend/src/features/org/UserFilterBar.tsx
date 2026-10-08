import { ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ROLES } from '@/features/auth/api'

import { ACCOUNT_STATES, type AccountState } from './api'
import { SearchForm } from './SearchForm'
import { hasUserFilters, type UserFilters } from './user-filters'

export function UserFilterBar({
  filters,
  onChange,
}: {
  filters: UserFilters
  onChange: (filters: UserFilters) => void
}) {
  const { t } = useTranslation()
  const update = (changes: Partial<UserFilters>) => onChange({ ...filters, ...changes })

  const stateOptions: { value: AccountState | 'all'; label: string }[] = [
    { value: 'all', label: t('users.states.all') },
    ...ACCOUNT_STATES.map((state) => ({ value: state, label: t(`users.states.${state}`) })),
  ]

  return (
    <section aria-label={t('users.filtersLabel')} className="flex flex-wrap items-center gap-3">
      <SearchForm
        label={t('users.search')}
        submitLabel={t('users.searchSubmit')}
        clearLabel={t('users.clearSearch')}
        value={filters.search}
        onSubmit={(search) => update({ search })}
      />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" aria-label={t('users.rolesLabel')}>
            {filters.roles.length === 0
              ? t('users.rolesAll')
              : t('users.rolesSome', { count: filters.roles.length })}
            <ChevronDown aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem disabled={filters.roles.length === 0} onSelect={() => update({ roles: [] })}>
            {t('users.rolesAll')}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {ROLES.map((role) => (
            <DropdownMenuCheckboxItem
              key={role}
              checked={filters.roles.includes(role)}
              // Keeps the menu open, so several roles can be picked at once.
              onSelect={(event) => event.preventDefault()}
              onCheckedChange={(checked) =>
                update({
                  roles: checked
                    ? [...filters.roles, role]
                    : filters.roles.filter((item) => item !== role),
                })
              }
            >
              {t(`roles.${role}`)}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <SegmentedControl
        label={t('users.stateLabel')}
        options={stateOptions}
        value={filters.state ?? 'all'}
        onChange={(state) => update({ state: state === 'all' ? undefined : state })}
      />

      {hasUserFilters(filters) && (
        <Button variant="ghost" size="sm" onClick={() => onChange({ search: '', roles: [] })}>
          {t('users.reset')}
        </Button>
      )}
    </section>
  )
}
