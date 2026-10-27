import { Copy, MailPlus } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { LoadFailed } from '@/components/LoadFailed'
import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import type { User } from '@/features/auth/api'
import { invitationLink } from '@/features/auth/invitation-link'
import { ActionForm, ActionNotice, type Notice } from '@/features/org/ActionForm'
import type { AssignableRole, Invitation, NewInvitation } from '@/features/org/api'
import { useCreateInvitation, useInvitations, useRevokeInvitation } from '@/features/org/hooks'
import { useOrganizationName } from '@/features/org/organization-column'
import { OrganizationField } from '@/features/org/OrganizationField'
import {
  canRevokeInvitation,
  invitableRoles,
  invitationState,
  type InvitationState,
} from '@/features/org/invitations'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

// The link, held only while it is shown once.
interface CreatedInvitation {
  email: string
  link: string
  expiresAt: string
}

// Enough to catch a slip; the API checks the address properly.
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Who is about to join: open invitations, with the used, revoked and
 * expired ones folded away. Admins and the owner invite; analysts read. */
export function InvitationsSection({ me }: { me: User }) {
  const { t } = useTranslation()
  const titleId = useId()
  const invitations = useInvitations()
  const create = useCreateInvitation()
  const revoke = useRevokeInvitation()
  const roles = invitableRoles(me)

  const [inviting, setInviting] = useState(false)
  const [created, setCreated] = useState<CreatedInvitation | null>(null)
  const [revoking, setRevoking] = useState<Invitation | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const pending = create.isPending || revoke.isPending

  const fail = (error: Error) =>
    setNotice({
      tone: 'error',
      text:
        error instanceof ApiError && error.status === 403
          ? t('invitations.forbidden')
          : error instanceof ApiError && error.status === 409
            ? t('invitations.taken')
            : error instanceof ApiError && error.status === 422
              ? t('invitations.invalid')
              : t('invitations.failed'),
    })

  const submitNew = (input: NewInvitation) => {
    setNotice(null)
    create.mutate(input, {
      onSuccess: (answer) => {
        setInviting(false)
        setCreated({
          email: answer.invitation.email,
          link: invitationLink(answer.token),
          expiresAt: answer.invitation.expires_at,
        })
        // The page's state is the only place the token lives.
        create.reset()
      },
      onError: fail,
    })
  }

  const confirmRevoke = (invitation: Invitation) =>
    revoke.mutate(invitation.id, {
      onSuccess: () => {
        setRevoking(null)
        setNotice({ tone: 'ok', text: t('invitations.revoked', { email: invitation.email }) })
      },
      onError: fail,
    })

  const startRevoke = (invitation: Invitation) => {
    setNotice(null)
    setInviting(false)
    setRevoking(invitation)
  }

  // States as of the list's loading, so they hold still between renders.
  const now = invitations.dataUpdatedAt
  const open = invitations.data?.filter((item) => invitationState(item, now) === 'open') ?? []
  const past = invitations.data?.filter((item) => invitationState(item, now) !== 'open') ?? []

  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id={titleId} className="font-medium">
          {t('invitations.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('invitations.subtitle')}</p>
      </div>

      {roles.length > 0 && (
        <div className="flex flex-col gap-3">
          {created ? (
            <NewInvitationPanel created={created} onDone={() => setCreated(null)} />
          ) : inviting ? (
            <InviteForm
              namesOrganization={me.role === 'owner'}
              roles={roles}
              pending={pending}
              onCancel={() => setInviting(false)}
              onSubmit={submitNew}
            />
          ) : revoking ? (
            <ActionForm
              title={t('invitations.revokeTitle', { email: revoking.email })}
              help={t('invitations.revokeHelp')}
              destructive
              pending={pending}
              onCancel={() => setRevoking(null)}
              onSubmit={() => confirmRevoke(revoking)}
            />
          ) : (
            <Button
              className="w-fit"
              onClick={() => {
                setNotice(null)
                setInviting(true)
              }}
            >
              <MailPlus aria-hidden />
              {t('invitations.invite')}
            </Button>
          )}
          {notice && <ActionNotice notice={notice} />}
        </div>
      )}

      {invitations.isPending ? (
        <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
        </div>
      ) : invitations.isError ? (
        <LoadFailed onRetry={invitations.refetch} />
      ) : (
        <>
          {open.length === 0 ? (
            <p className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
              {t('invitations.emptyOpen')}
            </p>
          ) : (
            <InvitationsTable
              label={t('invitations.openLabel')}
              invitations={open}
              now={now}
              canRevoke={(item) => canRevokeInvitation(me, item, now)}
              onRevoke={roles.length > 0 ? startRevoke : undefined}
              disabled={pending || created !== null}
            />
          )}
          {past.length > 0 && (
            <details className="group rounded-lg border bg-card">
              <summary className="cursor-pointer rounded-lg px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
                {t('invitations.history', { count: past.length })}
              </summary>
              <div className="border-t">
                <InvitationsTable
                  label={t('invitations.historyLabel')}
                  invitations={past}
                  now={now}
                  bare
                />
              </div>
            </details>
          )}
        </>
      )}
    </section>
  )
}

function InviteForm({
  namesOrganization,
  roles,
  pending,
  onCancel,
  onSubmit,
}: {
  // The platform owner invites into any organization; an admin into their own.
  namesOrganization: boolean
  roles: readonly AssignableRole[]
  pending: boolean
  onCancel: () => void
  onSubmit: (input: NewInvitation) => void
}) {
  const { t } = useTranslation()
  const emailId = useId()
  const emailHelpId = useId()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<AssignableRole>('user')
  const [organizationId, setOrganizationId] = useState<number | null>(null)
  const normalized = email.trim().toLowerCase()
  const organizationChosen = !namesOrganization || organizationId !== null

  return (
    <ActionForm
      title={t('invitations.formTitle')}
      help={t('invitations.formHelp')}
      confirmDisabled={!EMAIL_SHAPE.test(normalized) || !organizationChosen}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          email: normalized,
          role,
          ...(namesOrganization && organizationId !== null
            ? { organization_id: organizationId }
            : {}),
        })
      }
    >
      {namesOrganization && (
        <OrganizationField value={organizationId} onChange={setOrganizationId} />
      )}
      <div className="flex flex-col gap-1.5">
        <label htmlFor={emailId} className="text-sm font-medium">
          {t('invitations.email')}
        </label>
        <Input
          id={emailId}
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          aria-describedby={emailHelpId}
          autoFocus
          className="max-w-md bg-background"
        />
        <p id={emailHelpId} className="text-xs text-muted-foreground">
          {t('invitations.emailHelp')}
        </p>
      </div>
      <SegmentedControl
        label={t('invitations.role')}
        options={roles.map((value) => ({ value, label: t(`roles.${value}`) }))}
        value={role}
        onChange={setRole}
      />
    </ActionForm>
  )
}

/** The new link, shown this once. It lives in the page's state only: not in
 * the address, browser storage or the query cache. */
function NewInvitationPanel({
  created,
  onDone,
}: {
  created: CreatedInvitation
  onDone: () => void
}) {
  const { t } = useTranslation()
  const format = useFormatters()
  const titleId = useId()
  const [copy, setCopy] = useState<'copied' | 'failed' | null>(null)

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(created.link)
      setCopy('copied')
    } catch {
      setCopy('failed')
    }
  }

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-lg border border-sev-ok/40 bg-sev-ok-bg/40 px-4 py-4"
    >
      <div className="flex flex-col gap-1">
        <h3 id={titleId} className="font-medium">
          {t('invitations.created', { email: created.email })}
        </h3>
        <p className="max-w-prose text-sm text-muted-foreground">
          {t('invitations.createdHelp', { time: format.dateTime(created.expiresAt) })}
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">{t('invitations.linkLabel')}</span>
        <code className="rounded-md border bg-background px-3 py-2 font-mono text-xs break-all select-all">
          {created.link}
        </code>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => void copyLink()}>
          <Copy aria-hidden />
          {t('invitations.copy')}
        </Button>
        <Button onClick={onDone}>{t('invitations.saved')}</Button>
        <span role="status" className="text-sm text-muted-foreground">
          {copy === 'copied'
            ? t('invitations.copied')
            : copy === 'failed'
              ? t('invitations.copyFailed')
              : ''}
        </span>
      </div>
    </section>
  )
}

const STATE_STYLES: Record<InvitationState, string> = {
  open: 'bg-sev-ok-bg text-sev-ok',
  accepted: 'bg-brand-tint text-brand',
  expired: 'bg-muted text-muted-foreground',
  revoked: 'bg-sev-incident-bg text-sev-incident',
}

/** Always a word, never color alone. */
function InvitationStateBadge({ state }: { state: InvitationState }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        STATE_STYLES[state],
      )}
    >
      {t(`invitations.states.${state}`)}
    </span>
  )
}

/** When the invitation reached its state, or, while open, when it expires. */
function stateTime(invitation: Invitation, state: InvitationState): string {
  if (state === 'accepted') return invitation.accepted_at ?? invitation.expires_at
  if (state === 'revoked') return invitation.revoked_at ?? invitation.expires_at
  return invitation.expires_at
}

function InvitationsTable({
  label,
  invitations,
  now,
  canRevoke = () => false,
  onRevoke,
  disabled = false,
  bare = false,
}: {
  label: string
  invitations: Invitation[]
  now: number
  // Only for those who invite; each row asks whether its role is theirs to withdraw.
  canRevoke?: (invitation: Invitation) => boolean
  onRevoke?: (invitation: Invitation) => void
  disabled?: boolean
  // Inside another bordered box.
  bare?: boolean
}) {
  const { t } = useTranslation()
  const format = useFormatters()
  const organizationOf = useOrganizationName()

  return (
    <div className={cn('w-full overflow-x-auto', !bare && 'rounded-lg border bg-card')}>
      <table aria-label={label} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('invitations.person')}
            </th>
            {/* On phones the role and state move under the email. */}
            {organizationOf && (
              <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
                {t('organizations.column')}
              </th>
            )}
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('invitations.role')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('invitations.state')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">
              {t('invitations.when')}
            </th>
            {onRevoke && (
              <th scope="col" className="px-4 py-2.5 font-medium">
                <span className="sr-only">{t('invitations.actions')}</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {invitations.map((invitation) => {
            const state = invitationState(invitation, now)
            const time = stateTime(invitation, state)
            return (
              <tr key={invitation.id} className="border-b last:border-b-0">
                <td className="min-w-56 px-4 py-2.5">
                  <div className="flex flex-col gap-0.5">
                    {state === 'accepted' && invitation.accepted_user_id !== null ? (
                      <Link
                        to={`/org/users/${invitation.accepted_user_id}`}
                        className="w-fit rounded-sm font-mono text-xs font-medium break-all hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                      >
                        {invitation.email}
                      </Link>
                    ) : (
                      <span className="font-mono text-xs font-medium break-all">
                        {invitation.email}
                      </span>
                    )}
                    <span className="font-mono text-xs text-muted-foreground">
                      sci_{invitation.prefix}_…
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-2 sm:hidden">
                      <span className="text-xs">{t(`roles.${invitation.role}`)}</span>
                      <InvitationStateBadge state={state} />
                      {organizationOf && (
                        <span className="text-xs text-muted-foreground">
                          {organizationOf(invitation.organization_id)}
                        </span>
                      )}
                    </span>
                  </div>
                </td>
                {organizationOf && (
                  <td className="hidden max-w-40 truncate px-4 py-2.5 sm:table-cell">
                    {organizationOf(invitation.organization_id)}
                  </td>
                )}
                <td className="hidden px-4 py-2.5 whitespace-nowrap sm:table-cell">
                  {t(`roles.${invitation.role}`)}
                </td>
                <td className="hidden px-4 py-2.5 sm:table-cell">
                  <InvitationStateBadge state={state} />
                </td>
                <td className="hidden px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground md:table-cell">
                  <time dateTime={time} title={format.dateTime(time)}>
                    {state === 'open'
                      ? t('invitations.expiresIn', { time: format.relative(time) })
                      : format.date(time)}
                  </time>
                </td>
                {onRevoke && (
                  <td className="px-4 py-2.5 text-right">
                    {canRevoke(invitation) && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        aria-label={t('invitations.revokeLabel', { email: invitation.email })}
                        onClick={() => onRevoke(invitation)}
                      >
                        {t('invitations.revoke')}
                      </Button>
                    )}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
