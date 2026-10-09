import { useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, RefreshCw } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { LoadFailed } from '@/components/LoadFailed'
import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrentUser } from '@/features/auth/hooks'
import { ActionForm, ActionNotice, ConfirmForm, type Notice } from '@/features/org/ActionForm'
import {
  type ApiKey,
  KEY_LIFETIMES,
  type KeyLifetime,
  type NewApiKey,
} from '@/features/org/api'
import {
  KEY_NAME_MAX,
  keyState,
  type KeyState,
  SOURCE_MAX,
  sourceProblem,
  validKeyName,
} from '@/features/org/api-keys'
import { apiKeysKey, useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/features/org/hooks'
import { canManageApiKeys } from '@/features/org/permissions'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import { cn } from '@/lib/utils'

// The full key, held only while it is shown once.
interface CreatedKey {
  name: string
  key: string
}

export function OrgApiKeysPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: me } = useCurrentUser()
  const keys = useApiKeys()
  const create = useCreateApiKey()
  const revoke = useRevokeApiKey()
  const manages = me !== undefined && canManageApiKeys(me)

  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState<CreatedKey | null>(null)
  const [revoking, setRevoking] = useState<ApiKey | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const pending = create.isPending || revoke.isPending

  const fail = (error: Error) =>
    setNotice({
      tone: 'error',
      text:
        error instanceof ApiError && error.status === 403
          ? t('apiKeys.forbidden')
          : error instanceof ApiError && error.status === 422
            ? t('apiKeys.invalid')
            : t('apiKeys.failed'),
    })

  const submitNew = (input: NewApiKey) => {
    setNotice(null)
    create.mutate(input, {
      onSuccess: (answer) => {
        setCreating(false)
        setCreated({ name: answer.api_key.name, key: answer.key })
        // The page's state is the only place the full key lives.
        create.reset()
      },
      onError: fail,
    })
  }

  const confirmRevoke = (key: ApiKey) =>
    revoke.mutate(key.id, {
      onSuccess: () => {
        setRevoking(null)
        setNotice({ tone: 'ok', text: t('apiKeys.revoked', { name: key.name }) })
      },
      onError: fail,
    })

  const startRevoke = (key: ApiKey) => {
    setNotice(null)
    setCreating(false)
    setRevoking(key)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold">{t('nav.apiKeys')}</h1>
          <p className="max-w-prose text-muted-foreground">{t('apiKeys.subtitle')}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => void queryClient.resetQueries({ queryKey: apiKeysKey })}
        >
          <RefreshCw aria-hidden />
          {t('orgLog.refresh')}
        </Button>
      </header>

      {manages ? (
        <div className="flex flex-col gap-3">
          {created ? (
            <NewKeyPanel created={created} onDone={() => setCreated(null)} />
          ) : creating ? (
            <CreateKeyForm
              pending={pending}
              onCancel={() => setCreating(false)}
              onSubmit={submitNew}
            />
          ) : revoking ? (
            <ConfirmForm
              title={t('apiKeys.revokeTitle', { name: revoking.name })}
              help={t('apiKeys.revokeHelp')}
              destructive
              pending={pending}
              onCancel={() => setRevoking(null)}
              onConfirm={() => confirmRevoke(revoking)}
            />
          ) : (
            <Button
              className="w-fit"
              onClick={() => {
                setNotice(null)
                setCreating(true)
              }}
            >
              <KeyRound aria-hidden />
              {t('apiKeys.create')}
            </Button>
          )}
          {notice && <ActionNotice notice={notice} />}
        </div>
      ) : (
        <p className="rounded-lg border bg-card px-4 py-3 text-muted-foreground">
          {t('apiKeys.ownerOnly')}
        </p>
      )}

      {keys.isPending ? (
        <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : keys.isError ? (
        <LoadFailed onRetry={keys.refetch} />
      ) : keys.data.length === 0 ? (
        <p className="rounded-lg border bg-card px-4 py-4 text-muted-foreground">
          {t('apiKeys.empty')}
        </p>
      ) : (
        <KeysTable
          keys={keys.data}
          onRevoke={manages ? startRevoke : undefined}
          disabled={pending || created !== null}
        />
      )}
    </div>
  )
}

function CreateKeyForm({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean
  onCancel: () => void
  onSubmit: (input: NewApiKey) => void
}) {
  const { t } = useTranslation()
  const nameId = useId()
  const nameHelpId = useId()
  const sourceId = useId()
  const sourceHelpId = useId()
  const [name, setName] = useState('')
  const [source, setSource] = useState('')
  const [lifetime, setLifetime] = useState<KeyLifetime>(90)

  const problem = sourceProblem(source)
  // A problem shows once something is typed, not on an empty field.
  const sourceError =
    source.trim() === '' || problem === null
      ? null
      : problem === 'reserved'
        ? t('apiKeys.sourceReserved')
        : t('apiKeys.sourceFormat')
  const valid = validKeyName(name) && problem === null

  return (
    <ActionForm
      title={t('apiKeys.createTitle')}
      help={t('apiKeys.createHelp')}
      confirmDisabled={!valid}
      pending={pending}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          name: name.trim(),
          source: source.trim().toLowerCase(),
          expiresInDays: lifetime,
        })
      }
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={nameId} className="text-sm font-medium">
          {t('apiKeys.name')}
        </label>
        <Input
          id={nameId}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={KEY_NAME_MAX}
          aria-describedby={nameHelpId}
          autoFocus
          className="max-w-md bg-background"
        />
        <p id={nameHelpId} className="text-xs text-muted-foreground">
          {t('apiKeys.nameHelp')}
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={sourceId} className="text-sm font-medium">
          {t('apiKeys.source')}
        </label>
        <Input
          id={sourceId}
          value={source}
          onChange={(event) => setSource(event.target.value)}
          maxLength={SOURCE_MAX}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={sourceError !== null}
          aria-describedby={sourceHelpId}
          className="max-w-xs bg-background font-mono"
        />
        <p
          id={sourceHelpId}
          className={cn('text-xs', sourceError ? 'text-sev-incident' : 'text-muted-foreground')}
        >
          {sourceError ?? t('apiKeys.sourceHelp')}
        </p>
      </div>
      <SegmentedControl
        label={t('apiKeys.lifetime')}
        options={KEY_LIFETIMES.map((days) => ({
          value: String(days) as `${KeyLifetime}`,
          label: t(`apiKeys.lifetimes.${days}`),
        }))}
        value={String(lifetime) as `${KeyLifetime}`}
        onChange={(value) => setLifetime(Number(value) as KeyLifetime)}
      />
    </ActionForm>
  )
}

/** The new key, shown this once. It lives in the page's state only: not in
 * the address, browser storage or the query cache. */
function NewKeyPanel({ created, onDone }: { created: CreatedKey; onDone: () => void }) {
  const { t } = useTranslation()
  const titleId = useId()
  const [copy, setCopy] = useState<'copied' | 'failed' | null>(null)

  const copyKey = async () => {
    try {
      await navigator.clipboard.writeText(created.key)
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
        <h2 id={titleId} className="font-medium">
          {t('apiKeys.created', { name: created.name })}
        </h2>
        <p className="max-w-prose text-sm text-muted-foreground">{t('apiKeys.createdHelp')}</p>
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">{t('apiKeys.keyLabel')}</span>
        <code
          className="rounded-md border bg-background px-3 py-2 font-mono text-xs break-all select-all"
        >
          {created.key}
        </code>
        <p className="text-xs text-muted-foreground">
          {t('apiKeys.usage')}{' '}
          <code className="font-mono">Authorization: Bearer sck_…</code>
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => void copyKey()}>
          <Copy aria-hidden />
          {t('apiKeys.copy')}
        </Button>
        <Button onClick={onDone}>{t('apiKeys.saved')}</Button>
        <span role="status" className="text-sm text-muted-foreground">
          {copy === 'copied' ? t('apiKeys.copied') : copy === 'failed' ? t('apiKeys.copyFailed') : ''}
        </span>
      </div>
    </section>
  )
}

const STATE_STYLES: Record<KeyState, string> = {
  active: 'bg-sev-ok-bg text-sev-ok',
  expired: 'bg-muted text-muted-foreground',
  revoked: 'bg-sev-incident-bg text-sev-incident',
}

/** Always a word, never color alone. */
function KeyStateBadge({ state }: { state: KeyState }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        STATE_STYLES[state],
      )}
    >
      {t(`apiKeys.states.${state}`)}
    </span>
  )
}

function KeysTable({
  keys,
  onRevoke,
  disabled,
}: {
  keys: ApiKey[]
  // Only for the owner, and only on keys still active.
  onRevoke?: (key: ApiKey) => void
  disabled: boolean
}) {
  const { t } = useTranslation()
  const format = useFormatters()

  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table aria-label={t('apiKeys.tableLabel')} className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th scope="col" className="px-4 py-2.5 font-medium">
              {t('apiKeys.key')}
            </th>
            {/* On phones the source and state move under the name. */}
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('apiKeys.source')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">
              {t('apiKeys.state')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">
              {t('apiKeys.expires')}
            </th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">
              {t('apiKeys.lastUsed')}
            </th>
            {onRevoke && (
              <th scope="col" className="px-4 py-2.5 font-medium">
                <span className="sr-only">{t('apiKeys.actions')}</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const state = keyState(key)
            return (
              <tr key={key.id} className="border-b last:border-b-0">
                <td className="min-w-48 px-4 py-2.5">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">{key.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      sck_{key.prefix}_…
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-2 sm:hidden">
                      <span className="font-mono text-xs">{key.source}</span>
                      <KeyStateBadge state={state} />
                    </span>
                  </div>
                </td>
                <td className="hidden px-4 py-2.5 font-mono text-xs sm:table-cell">{key.source}</td>
                <td className="hidden px-4 py-2.5 sm:table-cell">
                  <KeyStateBadge state={state} />
                </td>
                <td className="hidden px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground md:table-cell">
                  <time dateTime={key.expires_at} title={format.dateTime(key.expires_at)}>
                    {format.date(key.expires_at)}
                  </time>
                </td>
                <td className="hidden px-4 py-2.5 font-mono text-xs whitespace-nowrap text-muted-foreground md:table-cell">
                  {key.last_used_at ? (
                    <time dateTime={key.last_used_at} title={format.dateTime(key.last_used_at)}>
                      {format.relative(key.last_used_at)}
                    </time>
                  ) : (
                    t('apiKeys.never')
                  )}
                </td>
                {onRevoke && (
                  <td className="px-4 py-2.5 text-right">
                    {state === 'active' && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        aria-label={t('apiKeys.revokeLabel', { name: key.name })}
                        onClick={() => onRevoke(key)}
                      >
                        {t('apiKeys.revoke')}
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
