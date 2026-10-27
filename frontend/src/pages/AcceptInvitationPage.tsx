import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router'

import { PublicShell } from '@/components/layout/PublicShell'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  acceptInvitation,
  type InvitationPreview,
  previewInvitation,
  USERNAME_MAX,
  validNewPassword,
  validUsername,
} from '@/features/auth/api'
import { tokenFromHash } from '@/features/auth/invitation-link'
import { ApiError } from '@/lib/api'
import { useFormatters } from '@/lib/format'
import type { LoginState } from '@/pages/LoginPage'

function isNotValid(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

/** Where an invited person picks a username and a password. The token comes
 * from the link's fragment, which is read once and then cleared from the
 * address bar and the history entry. */
export function AcceptInvitationPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [token] = useState(() => tokenFromHash(location.hash))

  useEffect(() => {
    if (location.hash !== '') {
      void navigate({ pathname: location.pathname, search: location.search }, { replace: true })
    }
  }, [location.hash, location.pathname, location.search, navigate])

  const preview = useQuery({
    // Not keyed by the token, and dropped when the page closes, so the
    // token is kept nowhere but here.
    queryKey: ['invitation-preview'],
    queryFn: ({ signal }) => previewInvitation(token ?? '', signal),
    enabled: token !== null,
    gcTime: 0,
    staleTime: Infinity,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const notValid = (
    <Alert variant="destructive" role="alert">
      <AlertDescription>{t('invite.notValid')}</AlertDescription>
    </Alert>
  )

  return (
    <PublicShell title={t('invite.title')} subtitle={t('invite.subtitle')}>
      {token === null ? (
        notValid
      ) : preview.isPending ? (
        <div role="status" aria-label={t('app.loading')} className="flex flex-col gap-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : preview.isError ? (
        isNotValid(preview.error) ? (
          notValid
        ) : (
          <div className="flex flex-col gap-3">
            <Alert variant="destructive" role="alert">
              <AlertDescription>{t('invite.errors.network')}</AlertDescription>
            </Alert>
            <Button variant="outline" className="w-fit" onClick={() => void preview.refetch()}>
              {t('invite.retry')}
            </Button>
          </div>
        )
      ) : (
        <AcceptForm
          token={token}
          invitation={preview.data}
          onAccepted={() =>
            void navigate('/login', {
              replace: true,
              state: { registeredEmail: preview.data.email } satisfies LoginState,
            })
          }
        />
      )}
    </PublicShell>
  )
}

function AcceptForm({
  token,
  invitation,
  onAccepted,
}: {
  token: string
  invitation: InvitationPreview
  onAccepted: () => void
}) {
  const { t } = useTranslation()
  const format = useFormatters()
  const usernameId = useId()
  const usernameHelpId = useId()
  const passwordId = useId()
  const passwordHelpId = useId()
  const repeatId = useId()
  const repeatHelpId = useId()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const accept = useMutation({ mutationFn: acceptInvitation, gcTime: 0 })

  const usernameOk = validUsername(username)
  const passwordOk = validNewPassword(password)
  const repeatOk = repeat === password
  // A problem shows once something is typed, not on an empty field.
  const usernameError = username !== '' && !usernameOk
  const passwordError = password !== '' && !passwordOk
  const repeatError = repeat !== '' && !repeatOk

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    accept.mutate({ token, username, password }, { onSuccess: onAccepted })
  }

  if (accept.isError && isNotValid(accept.error)) {
    return (
      <Alert variant="destructive" role="alert">
        <AlertDescription>{t('invite.notValid')}</AlertDescription>
      </Alert>
    )
  }

  const error = !accept.isError
    ? null
    : accept.error instanceof ApiError && accept.error.status === 400
      ? t('invite.errors.usernameTaken')
      : accept.error instanceof ApiError && accept.error.status === 422
        ? t('invite.errors.validation')
        : t('invite.errors.network')

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-muted-foreground">{t('invite.email')}</dt>
        <dd className="break-all">{invitation.email}</dd>
        <dt className="text-muted-foreground">{t('invite.role')}</dt>
        <dd>{t(`roles.${invitation.role}`)}</dd>
        <dt className="text-muted-foreground">{t('invite.expires')}</dt>
        <dd>
          <time dateTime={invitation.expires_at} title={format.dateTime(invitation.expires_at)}>
            {format.relative(invitation.expires_at)}
          </time>
        </dd>
      </dl>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Sign-in is by email: this lets a password manager file the new
          password under it, not under the username. */}
      <input
        type="text"
        autoComplete="username"
        value={invitation.email}
        readOnly
        hidden
        tabIndex={-1}
      />

      <div className="flex flex-col gap-2">
        <Label htmlFor={usernameId}>{t('invite.username')}</Label>
        <Input
          id={usernameId}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          required
          maxLength={USERNAME_MAX}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          aria-invalid={usernameError}
          aria-describedby={usernameHelpId}
          autoFocus
        />
        <p
          id={usernameHelpId}
          className={usernameError ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}
        >
          {t('invite.usernameHelp')}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={passwordId}>{t('invite.password')}</Label>
        <Input
          id={passwordId}
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={passwordError}
          aria-describedby={passwordHelpId}
        />
        <p
          id={passwordHelpId}
          className={passwordError ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}
        >
          {t('invite.passwordHelp')}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={repeatId}>{t('invite.repeat')}</Label>
        <Input
          id={repeatId}
          type="password"
          autoComplete="new-password"
          required
          value={repeat}
          onChange={(event) => setRepeat(event.target.value)}
          aria-invalid={repeatError}
          aria-describedby={repeatError ? repeatHelpId : undefined}
        />
        {repeatError && (
          <p id={repeatHelpId} className="text-xs text-destructive">
            {t('invite.repeatMismatch')}
          </p>
        )}
      </div>

      <Button
        type="submit"
        disabled={!usernameOk || !passwordOk || !repeatOk || accept.isPending}
        className="mt-2"
      >
        {accept.isPending ? t('invite.submitting') : t('invite.submit')}
      </Button>
    </form>
  )
}
