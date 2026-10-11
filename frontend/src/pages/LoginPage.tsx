import { useState, type FormEvent } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'

import { PublicShell } from '@/components/layout/PublicShell'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { isAccountLockedError } from '@/features/auth/api'
import { useCurrentUser, useLogIn } from '@/features/auth/hooks'
import { safeNextPath } from '@/features/auth/redirect'
import { ApiError } from '@/lib/api'

function loginErrorMessage(error: unknown, t: TFunction): string {
  if (!(error instanceof ApiError)) {
    return t('login.errors.network')
  }
  switch (error.status) {
    case 401:
      return t('login.errors.invalid')
    case 403:
      return isAccountLockedError(error) ? t('login.errors.accountLocked') : t('login.errors.inactive')
    case 422:
      return t('login.errors.validation')
    case 429: {
      const minutes = Math.max(1, Math.ceil((error.retryAfterSeconds ?? 60) / 60))
      return t('login.errors.locked', { count: minutes })
    }
    default:
      return t('login.errors.network')
  }
}

/** Router state left by the invitation page, so the new account's email
 * never goes through the address. */
export interface LoginState {
  registeredEmail?: string
}

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))
  const currentUser = useCurrentUser()
  const logIn = useLogIn()
  const registeredEmail = (location.state as LoginState | null)?.registeredEmail
  const [email, setEmail] = useState(registeredEmail ?? '')
  const [password, setPassword] = useState('')

  if (currentUser.isSuccess) {
    return <Navigate to={next} replace />
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    logIn.mutate(
      { email, password },
      { onSuccess: () => void navigate(next, { replace: true }) },
    )
  }

  const reason = params.get('reason')
  const error = logIn.isError
    ? loginErrorMessage(logIn.error, t)
    : reason === 'inactive'
      ? t('login.errors.inactive')
      : reason === 'locked'
        ? t('login.errors.accountLocked')
        : null

  return (
    <PublicShell title={t('login.title')} subtitle={t('login.subtitle')}>
      <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        {error ? (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : (
          registeredEmail && (
            <Alert role="status">
              <AlertDescription>{t('login.registered')}</AlertDescription>
            </Alert>
          )
        )}

        <div className="flex flex-col gap-2">
          <Label htmlFor="login-email">{t('login.email')}</Label>
          <Input
            id="login-email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="login-password">{t('login.password')}</Label>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            // The new account's email is filled in; its password is next.
            autoFocus={registeredEmail !== undefined}
          />
        </div>

        <Button type="submit" disabled={logIn.isPending} className="mt-2">
          {logIn.isPending ? t('login.submitting') : t('login.submit')}
        </Button>
      </form>
    </PublicShell>
  )
}
