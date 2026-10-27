import { useQueryClient } from '@tanstack/react-query'
import { Building2, RefreshCw } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { LoadFailed } from '@/components/LoadFailed'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ActionForm, ActionNotice, type Notice } from '@/features/org/ActionForm'
import type { NewOrganization, Organization } from '@/features/org/api'
import {
  organizationsKey,
  useCreateOrganization,
  useOrganizations,
  useReactivateOrganization,
  useRenameOrganization,
  useSuspendOrganization,
} from '@/features/org/hooks'
import {
  ORGANIZATION_NAME_MAX,
  SLUG_MAX,
  slugFrom,
  validOrganizationName,
  validSlug,
} from '@/features/org/organizations'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

// The one action in progress: at most one form shows at a time.
type Step =
  | { kind: 'create' }
  | { kind: 'rename' | 'suspend' | 'reactivate'; organization: Organization }

/** The platform's organizations, for its owner only: create, rename,
 * suspend and reactivate. None is ever deleted, so its records stay. */
export function OrgOrganizationsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const organizations = useOrganizations(true)
  const create = useCreateOrganization()
  const rename = useRenameOrganization()
  const suspend = useSuspendOrganization()
  const reactivate = useReactivateOrganization()
  const [step, setStep] = useState<Step | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const pending = create.isPending || rename.isPending || suspend.isPending || reactivate.isPending

  const fail = (error: Error) =>
    setNotice({
      tone: 'error',
      text:
        error instanceof ApiError && error.status === 409
          ? t('organizations.taken')
          : error instanceof ApiError && error.status === 422
            ? t('organizations.invalid')
            : t('organizations.failed'),
    })
  const done = (text: string) => {
    setStep(null)
    setNotice({ tone: 'ok', text })
  }
  const start = (next: Step) => {
    setNotice(null)
    setStep(next)
  }

  const submitNew = (input: NewOrganization) =>
    create.mutate(input, {
      onSuccess: (organization) =>
        done(t('organizations.createdDone', { name: organization.name })),
      onError: fail,
    })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t('nav.organizations')}
        description={t('organizations.subtitle')}
        actions={
          <Button
            variant="outline"
            onClick={() => void queryClient.resetQueries({ queryKey: organizationsKey })}
          >
            <RefreshCw aria-hidden />
            {t('orgLog.refresh')}
          </Button>
        }
      />

      <div className="flex flex-col gap-3">
        {step?.kind === 'create' ? (
          <CreateForm pending={pending} onCancel={() => setStep(null)} onSubmit={submitNew} />
        ) : step?.kind === 'rename' ? (
          <RenameForm
            key={step.organization.id}
            organization={step.organization}
            pending={pending}
            onCancel={() => setStep(null)}
            onSubmit={(name) =>
              rename.mutate(
                { id: step.organization.id, name },
                {
                  onSuccess: (organization) =>
                    done(t('organizations.renamedDone', { name: organization.name })),
                  onError: fail,
                },
              )
            }
          />
        ) : step?.kind === 'suspend' ? (
          <SuspendForm
            key={step.organization.id}
            organization={step.organization}
            pending={pending}
            onCancel={() => setStep(null)}
            onConfirm={() =>
              suspend.mutate(step.organization.id, {
                onSuccess: (organization) =>
                  done(t('organizations.suspendedDone', { name: organization.name })),
                onError: fail,
              })
            }
          />
        ) : step?.kind === 'reactivate' ? (
          <ActionForm
            title={t('organizations.reactivateTitle', { name: step.organization.name })}
            help={t('organizations.reactivateHelp')}
            pending={pending}
            onCancel={() => setStep(null)}
            onSubmit={() =>
              reactivate.mutate(step.organization.id, {
                onSuccess: (organization) =>
                  done(t('organizations.reactivatedDone', { name: organization.name })),
                onError: fail,
              })
            }
          />
        ) : (
          <Button className="w-fit" onClick={() => start({ kind: 'create' })}>
            <Building2 aria-hidden />
            {t('organizations.create')}
          </Button>
        )}
        {notice && <ActionNotice notice={notice} />}
      </div>

      {organizations.isPending ? (
        <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : organizations.isError ? (
        <LoadFailed onRetry={organizations.refetch} />
      ) : organizations.data.length === 0 ? (
        <p className="rounded-lg border bg-card px-4 py-4 text-muted-foreground">
          {t('organizations.empty')}
        </p>
      ) : (
        <OrganizationsTable
          organizations={organizations.data}
          disabled={pending}
          onAction={(kind, organization) => start({ kind, organization })}
        />
      )}
    </div>
  )
}

function CreateForm({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean
  onCancel: () => void
  onSubmit: (input: NewOrganization) => void
}) {
  const { t } = useTranslation()
  const nameId = useId()
  const nameHelpId = useId()
  const slugId = useId()
  const slugHelpId = useId()
  const [name, setName] = useState('')
  // Follows the name until it is edited by hand.
  const [slug, setSlug] = useState<string | null>(null)
  const shownSlug = slug ?? slugFrom(name)
  const slugError = shownSlug !== '' && !validSlug(shownSlug)

  return (
    <ActionForm
      title={t('organizations.createTitle')}
      help={t('organizations.createHelp')}
      confirmDisabled={!validOrganizationName(name) || !validSlug(shownSlug)}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() => onSubmit({ name: name.trim(), slug: shownSlug })}
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={nameId} className="text-sm font-medium">
          {t('organizations.name')}
        </label>
        <Input
          id={nameId}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={ORGANIZATION_NAME_MAX}
          aria-describedby={nameHelpId}
          autoFocus
          className="max-w-md bg-background"
        />
        <p id={nameHelpId} className="text-xs text-muted-foreground">
          {t('organizations.nameHelp')}
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={slugId} className="text-sm font-medium">
          {t('organizations.slug')}
        </label>
        <Input
          id={slugId}
          value={shownSlug}
          onChange={(event) => setSlug(event.target.value)}
          maxLength={SLUG_MAX}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={slugError}
          aria-describedby={slugHelpId}
          className="max-w-xs bg-background font-mono"
        />
        <p
          id={slugHelpId}
          className={cn('text-xs', slugError ? 'text-sev-incident' : 'text-muted-foreground')}
        >
          {t('organizations.slugHelp')}
        </p>
      </div>
    </ActionForm>
  )
}

function RenameForm({
  organization,
  pending,
  onCancel,
  onSubmit,
}: {
  organization: Organization
  pending: boolean
  onCancel: () => void
  onSubmit: (name: string) => void
}) {
  const { t } = useTranslation()
  const nameId = useId()
  const [name, setName] = useState(organization.name)
  const changed = name.trim() !== organization.name

  return (
    <ActionForm
      title={t('organizations.renameTitle', { name: organization.name })}
      help={t('organizations.renameHelp', { slug: organization.slug })}
      confirmDisabled={!validOrganizationName(name) || !changed}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() => onSubmit(name.trim())}
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={nameId} className="text-sm font-medium">
          {t('organizations.name')}
        </label>
        <Input
          id={nameId}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={ORGANIZATION_NAME_MAX}
          autoFocus
          className="max-w-md bg-background"
        />
      </div>
    </ActionForm>
  )
}

/** Suspending signs out every member at once, so the owner types the slug
 * first, as a deliberate step that a stray click cannot take. */
function SuspendForm({
  organization,
  pending,
  onCancel,
  onConfirm,
}: {
  organization: Organization
  pending: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const { t } = useTranslation()
  const confirmId = useId()
  const [typed, setTyped] = useState('')

  return (
    <ActionForm
      title={t('organizations.suspendTitle', { name: organization.name })}
      help={t('organizations.suspendHelp')}
      destructive
      confirmDisabled={typed.trim() !== organization.slug}
      pending={pending}
      onCancel={onCancel}
      onSubmit={onConfirm}
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={confirmId} className="text-sm font-medium">
          {t('organizations.suspendConfirm', { slug: organization.slug })}
        </label>
        <Input
          id={confirmId}
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          autoFocus
          className="max-w-xs bg-background font-mono"
        />
      </div>
    </ActionForm>
  )
}

function OrganizationsTable({
  organizations,
  disabled,
  onAction,
}: {
  organizations: Organization[]
  disabled: boolean
  onAction: (kind: 'rename' | 'suspend' | 'reactivate', organization: Organization) => void
}) {
  const { t } = useTranslation()
  const format = useFormatters()

  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table aria-label={t('organizations.tableLabel')} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('organizations.organization')}
            </th>
            {/* On phones the state and members move under the name. */}
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('organizations.state')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">
              {t('organizations.members')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">
              {t('organizations.createdAt')}
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              <span className="sr-only">{t('organizations.actions')}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {organizations.map((organization) => {
            const suspended = organization.suspended_at !== null
            return (
              <tr key={organization.id} className="border-b last:border-b-0">
                <td className="min-w-48 px-4 py-2.5">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">{organization.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">{organization.slug}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-2 sm:hidden">
                      <OrganizationStateBadge suspended={suspended} />
                      <span className="text-xs text-muted-foreground">
                        {t('organizations.members')}: {format.number(organization.members)}
                      </span>
                    </span>
                  </div>
                </td>
                <td className="hidden px-4 py-2.5 sm:table-cell">
                  <OrganizationStateBadge suspended={suspended} />
                </td>
                <td className="hidden px-4 py-2.5 text-right font-mono text-xs tabular-nums sm:table-cell">
                  {format.number(organization.members)}
                </td>
                <td className="hidden px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground md:table-cell">
                  <time dateTime={organization.created_at} title={format.dateTime(organization.created_at)}>
                    {format.date(organization.created_at)}
                  </time>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={disabled}
                      aria-label={t('organizations.renameLabel', { name: organization.name })}
                      onClick={() => onAction('rename', organization)}
                    >
                      {t('organizations.rename')}
                    </Button>
                    {suspended ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        aria-label={t('organizations.reactivateLabel', { name: organization.name })}
                        onClick={() => onAction('reactivate', organization)}
                      >
                        {t('organizations.reactivate')}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        aria-label={t('organizations.suspendLabel', { name: organization.name })}
                        onClick={() => onAction('suspend', organization)}
                      >
                        {t('organizations.suspend')}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Always a word, never color alone. */
function OrganizationStateBadge({ suspended }: { suspended: boolean }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex rounded-full px-2 py-0.5 text-xs whitespace-nowrap',
        suspended ? 'bg-sev-incident-bg text-sev-incident' : 'bg-sev-ok-bg text-sev-ok',
      )}
    >
      {t(suspended ? 'organizations.states.suspended' : 'organizations.states.active')}
    </span>
  )
}
