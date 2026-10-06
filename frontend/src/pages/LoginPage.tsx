import { useState, type FormEvent } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
      return t('login.errors.inactive')
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

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))
  const currentUser = useCurrentUser()
  const logIn = useLogIn()
  const [email, setEmail] = useState('')
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

  const error = logIn.isError
    ? loginErrorMessage(logIn.error, t)
    : params.get('reason') === 'inactive'
      ? t('login.errors.inactive')
      : null

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-md bg-primary font-mono text-xs font-semibold text-primary-foreground"
            >
              SC
            </span>
            {t('app.name')}
          </div>
          <h1 className="mt-4 text-2xl font-semibold text-balance">{t('login.title')}</h1>
          <p className="text-muted-foreground">{t('login.subtitle')}</p>
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
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
            />
          </div>

          <Button type="submit" disabled={logIn.isPending} className="mt-2">
            {logIn.isPending ? t('login.submitting') : t('login.submit')}
          </Button>
        </form>
      </div>
    </main>
  )
}
