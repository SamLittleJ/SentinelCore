import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { makeUser, server, signedInAs } from '@/test/server'

describe('route guards and navigation', () => {
  it('sends visitors without a session to the login page', async () => {
    signedInAs(null)
    const { router } = renderApp('/org/events')

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe('?next=%2Forg%2Fevents')
  })

  it('sends a deactivated user to the login page with an explanation', async () => {
    server.use(
      http.get('/api/users/me', () =>
        HttpResponse.json({ detail: 'Inactive user' }, { status: 403 }),
      ),
    )
    renderApp('/me')

    expect(await screen.findByRole('alert')).toHaveTextContent('Contul este dezactivat.')
  })

  it('sends a locked user to the login page with an explanation', async () => {
    server.use(
      http.get('/api/users/me', () =>
        HttpResponse.json({ detail: 'Account temporarily locked' }, { status: 403 }),
      ),
    )
    const { router } = renderApp('/me')

    expect(await screen.findByRole('alert')).toHaveTextContent('Contul este blocat temporar')
    expect(router.state.location.search).toBe('?reason=locked')
  })

  it('offers a retry when the API is unreachable', async () => {
    server.use(http.get('/api/users/me', () => HttpResponse.error()))
    renderApp('/me')

    // Network errors are retried twice (after 1 s and 2 s) before giving up.
    expect(
      await screen.findByRole('heading', { name: 'Datele nu s-au încărcat' }, { timeout: 6000 }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Încearcă din nou' })).toBeInTheDocument()
  }, 10_000)

  it('hides the organization perspective from regular users', async () => {
    signedInAs(makeUser('user'))
    renderApp('/me')

    await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })
    expect(screen.queryByRole('navigation', { name: 'Perspectivă' })).not.toBeInTheDocument()
  })

  it('blocks organization pages for regular users', async () => {
    signedInAs(makeUser('user'))
    renderApp('/org/users')

    expect(await screen.findByRole('heading', { name: 'Acces restricționat' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Înapoi la contul meu' })).toHaveAttribute('href', '/me')
  })

  it.each(['admin', 'owner', 'security_analyst'] as const)(
    'shows the organization and the account to %s',
    async (role) => {
      signedInAs(makeUser(role))
      renderApp('/org')

      // The owner looks at the whole platform; a member at their organization.
      const owner = role === 'owner'
      const nav = await screen.findByRole('navigation', { name: owner ? 'Platformă' : 'Acme' })
      expect(within(nav).getByRole('link', { name: 'Prezentare' })).toHaveAttribute('aria-current', 'page')
      expect(within(nav).getByRole('link', { name: 'Evenimente de securitate' })).toBeInTheDocument()
      expect(within(nav).getByRole('link', { name: 'Chei API' })).toBeInTheDocument()
      expect(within(nav).queryByRole('link', { name: 'Organizații' }) !== null).toBe(owner)
      const account = screen.getByRole('navigation', { name: 'Contul meu' })
      expect(within(account).getByRole('link', { name: 'Sesiunile mele' })).toBeInTheDocument()
    },
  )

  it("shows a user their account's pages only, without a group name", async () => {
    signedInAs(makeUser())
    renderApp('/me')

    const nav = await screen.findByRole('navigation', { name: 'Navigare principală' })
    expect(within(nav).getByRole('link', { name: 'Prezentare' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Sesiunile mele' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Utilizatori' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Chei API' })).not.toBeInTheDocument()
    expect(screen.queryByText('Contul meu')).not.toBeInTheDocument()
  })

  it('shows a not found page for unknown addresses', async () => {
    signedInAs(makeUser())
    renderApp('/nothing-here')

    expect(await screen.findByRole('heading', { name: 'Pagina nu există' })).toBeInTheDocument()
  })
})
