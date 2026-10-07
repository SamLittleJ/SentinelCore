import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { CSRF_COOKIE, CSRF_HEADER } from '@/lib/api'
import { renderApp } from '@/test/render'
import { makeUser, server, signedInAs } from '@/test/server'

async function openMenu() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Meniul contului' }))
  return user
}

describe('account menu', () => {
  it('starts in the dark theme', async () => {
    signedInAs(makeUser())
    renderApp('/me')

    await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })
    expect(document.documentElement).toHaveClass('dark')
  })

  it('switches to the light theme and remembers it', async () => {
    signedInAs(makeUser())
    renderApp('/me')

    const user = await openMenu()
    await user.click(screen.getByRole('menuitemradio', { name: 'Luminoasă' }))

    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem('sentinelcore.theme')).toBe('light')
  })

  it('switches the language to English and remembers it', async () => {
    signedInAs(makeUser('admin'))
    renderApp('/me')

    const user = await openMenu()
    await user.click(screen.getByRole('menuitemradio', { name: 'English' }))

    expect(await screen.findByRole('heading', { name: 'Welcome, elena.radu' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My sessions' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('sentinelcore.language')).toBe('en')
  })

  it('logs out with the CSRF token and returns to the login page', async () => {
    signedInAs(makeUser())
    document.cookie = `${CSRF_COOKIE}=csrf-abc; path=/`
    const logoutHeaders: (string | null)[] = []
    server.use(
      http.post('/api/auth/logout', ({ request }) => {
        logoutHeaders.push(request.headers.get(CSRF_HEADER))
        signedInAs(null)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { router } = renderApp('/me')

    const user = await openMenu()
    await user.click(screen.getByRole('menuitem', { name: 'Deconectare' }))

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(logoutHeaders).toEqual(['csrf-abc'])
  })

  it('returns to the login page when the session ends during use', async () => {
    signedInAs(makeUser())
    const { queryClient } = renderApp('/me')
    await screen.findByRole('heading', { name: 'Bun venit, elena.radu' })

    // The session was revoked elsewhere; the next check of the user fails.
    signedInAs(null)
    await queryClient.invalidateQueries()

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
  })
})
