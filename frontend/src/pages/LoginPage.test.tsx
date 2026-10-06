import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { makeUser, server, signedInAs } from '@/test/server'

async function submitLogin(email = 'elena.radu@example.com', password = 'testpassword') {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Parolă'), password)
  await user.click(screen.getByRole('button', { name: 'Autentifică-te' }))
}

function loginResponds(status: number, headers: Record<string, string> = {}) {
  const bodies: unknown[] = []
  server.use(
    http.post('/api/auth/session', async ({ request }) => {
      bodies.push(await request.json())
      if (status === 204) {
        signedInAs(makeUser())
        return new HttpResponse(null, { status: 204 })
      }
      return HttpResponse.json({ detail: 'error' }, { status, headers })
    }),
  )
  return bodies
}

describe('LoginPage', () => {
  it('logs in through the cookie endpoint and opens the account', async () => {
    signedInAs(null)
    const bodies = loginResponds(204)
    const { router } = renderApp('/login')

    await submitLogin()

    expect(await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/me')
    expect(bodies).toEqual([{ email: 'elena.radu@example.com', password: 'testpassword' }])
  })

  it('returns to the page that required login', async () => {
    signedInAs(makeUser('admin'))
    signedInAs(null)
    loginResponds(204)
    const { router } = renderApp('/me/sessions')

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?next=%2Fme%2Fsessions')

    await submitLogin()

    expect(await screen.findByRole('heading', { name: 'Sesiunile mele' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/me/sessions')
  })

  it('ignores a next parameter pointing to another site', async () => {
    signedInAs(null)
    loginResponds(204)
    const { router } = renderApp('/login?next=https://evil.example')

    await submitLogin()

    await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })
    expect(router.state.location.pathname).toBe('/me')
  })

  it.each([
    [401, {}, 'Email sau parolă greșite.'],
    [403, {}, 'Contul este dezactivat. Contactează un administrator.'],
    [422, {}, 'Verifică adresa de email și parola.'],
    [429, { 'Retry-After': '61' }, 'Prea multe încercări eșuate. Încearcă din nou peste 2 minute.'],
    [429, { 'Retry-After': '900' }, 'Prea multe încercări eșuate. Încearcă din nou peste 15 minute.'],
    [429, { 'Retry-After': '1200' }, 'Prea multe încercări eșuate. Încearcă din nou peste 20 de minute.'],
    [500, {}, 'Serverul nu răspunde. Verifică conexiunea și încearcă din nou.'],
  ])('shows a clear message for status %i', async (status, headers, message) => {
    signedInAs(null)
    loginResponds(status, headers)
    renderApp('/login')

    await submitLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('redirects a signed-in user away from the login page', async () => {
    signedInAs(makeUser())
    const { router } = renderApp('/login')

    await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })
    expect(router.state.location.pathname).toBe('/me')
  })
})
