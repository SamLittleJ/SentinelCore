import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useMemo, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import { PagedResults } from '@/components/PagedResults'
import { Button } from '@/components/ui/button'
import type { User } from '@/features/auth/api'
import { AccountState } from '@/features/org/AccountState'
import { userListKey, useUsers } from '@/features/org/hooks'
import { UserFilterBar } from '@/features/org/UserFilterBar'
import {
  hasUserFilters,
  readUserFilters,
  type UserFilters,
  type UserPageState,
  writeUserFilters,
} from '@/features/org/user-filters'
import { useFormatters } from '@/lib/format'

export function OrgUsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => readUserFilters(params), [params])
  const users = useUsers(filters)

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold">{t('nav.users')}</h1>
          <p className="max-w-prose text-muted-foreground">{t('users.subtitle')}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => void queryClient.resetQueries({ queryKey: userListKey })}
        >
          <RefreshCw aria-hidden />
          {t('orgLog.refresh')}
        </Button>
      </header>

      <UserFilterBar
        filters={filters}
        onChange={(next: UserFilters) => setParams(writeUserFilters(next))}
      />

      <PagedResults
        query={users}
        empty={hasUserFilters(filters) ? t('users.emptyFiltered') : t('users.empty')}
        end={t('users.end')}
      >
        {(items) => <UsersTable users={items} />}
      </PagedResults>
    </div>
  )
}

/** Each row opens the account: by keyboard through the username link, by
 * mouse anywhere on the row. */
function UsersTable({ users }: { users: User[] }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const navigate = useNavigate()
  const location = useLocation()
  const state: UserPageState = { from: location.pathname + location.search }

  const openRow = (event: MouseEvent, user: User) => {
    // The link handles its own clicks.
    if ((event.target as HTMLElement).closest('a')) return
    void navigate(`/org/users/${user.id}`, { state })
  }

  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table aria-label={t('users.tableLabel')} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('users.user')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('users.role')}
            </th>
            {/* On phones the state moves under the email, so it stays in view. */}
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('users.state')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">
              {t('users.memberSince')}
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr
              key={user.id}
              onClick={(event) => openRow(event, user)}
              className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-accent/40"
            >
              <td className="min-w-56 px-4 py-2.5">
                <div className="flex flex-col gap-0.5">
                  <Link
                    to={`/org/users/${user.id}`}
                    state={state}
                    className="w-fit rounded-sm font-medium hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                  >
                    {user.username}
                  </Link>
                  <span className="font-mono text-xs text-muted-foreground">{user.email}</span>
                  <span className="mt-1 sm:hidden">
                    <AccountState user={user} />
                  </span>
                </div>
              </td>
              <td className="px-4 py-2.5 whitespace-nowrap">{t(`roles.${user.role}`)}</td>
              <td className="hidden px-4 py-2.5 sm:table-cell">
                <AccountState user={user} />
              </td>
              <td className="hidden px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground md:table-cell">
                <time dateTime={user.created_at} title={format.dateTime(user.created_at)}>
                  {format.date(user.created_at)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
