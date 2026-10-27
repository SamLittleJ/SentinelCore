import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Role } from '@/features/auth/api'
import { renderApp } from '@/test/render'
import { makeSummary, makeUser, server, signedInAs } from '@/test/server'

async function openPalette(role: Role, path = '/me') {
  signedInAs(makeUser(role))
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1 })
  const user = userEvent.setup()
  await user.keyboard('{Control>}k{/Control}')
  const input = await screen.findByRole('combobox', { name: 'Comandă sau căutare' })
  return { ...result, user, input }
}

function options() {
  return within(screen.getByRole('listbox')).getAllByRole('option')
}

function location(router: { state: { location: { pathname: string; search: string } } }) {
  return router.state.location.pathname + router.state.location.search
}

describe('command palette', () => {
  it('opens with Ctrl+K and from the sidebar, and closes with Escape', async () => {
    const { user, input } = await openPalette('user')

    expect(input).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Caută sau sari la/ }))
    expect(await screen.findByRole('combobox')).toHaveFocus()
  })

  it('finds pages without diacritics and opens the highlighted one with Enter', async () => {
    const { user, input, router } = await openPalette('user')

    await user.type(input, 'sesiunile')

    expect(options().map((option) => option.textContent)).toEqual([
      expect.stringContaining('Sesiunile mele'),
    ])
    await user.keyboard('{Enter}')
    await waitFor(() => expect(location(router)).toBe('/me/sessions'))
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('moves through the list with the arrow keys, wrapping at the ends', async () => {
    const { user, input } = await openPalette('user')

    const first = options()[0]
    expect(input).toHaveAttribute('aria-activedescendant', first.id)
    expect(first).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{ArrowDown}')
    expect(input).toHaveAttribute('aria-activedescendant', options()[1].id)

    await user.keyboard('{ArrowUp}{ArrowUp}')
    const last = options().at(-1)
    expect(input).toHaveAttribute('aria-activedescendant', last?.id)
    expect(last).toHaveTextContent('Deconectare')
  })

  it('shows a user only their own pages, and no search of the organization', async () => {
    const { user, input } = await openPalette('user')

    expect(screen.queryByRole('option', { name: /Evenimente de securitate/ })).not.toBeInTheDocument()
    await user.type(input, 'elena@example.com')
    expect(screen.queryByRole('group', { name: 'Caută' })).not.toBeInTheDocument()
    expect(screen.getByText('Nicio comandă potrivită.')).toBeInTheDocument()
  })

  it('opens the filtered event log and user list for an operator, without asking the API itself', async () => {
    const requests: string[] = []
    server.events.on('request:start', ({ request }) => requests.push(new URL(request.url).pathname))
    const { user, input, router } = await openPalette('security_analyst', '/org/api-keys')
    requests.length = 0

    await user.type(input, '203.0.113.7')
    const search = within(screen.getByRole('group', { name: 'Caută' })).getAllByRole('option')
    expect(search.map((option) => option.textContent)).toEqual([
      expect.stringContaining('Caută „203.0.113.7” în utilizatori'),
      expect.stringContaining('Caută „203.0.113.7” în evenimentele de securitate'),
    ])
    // Typing sent nothing: only the page that opens loads (and audits) records.
    expect(requests).toEqual([])

    await user.keyboard('{ArrowDown}{Enter}')
    await waitFor(() => expect(location(router)).toBe('/org/events?q=203.0.113.7'))

    await user.keyboard('{Control>}k{/Control}')
    await user.type(await screen.findByRole('combobox'), 'radu')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(location(router)).toBe('/org/users?q=radu'))
    server.events.removeAllListeners()
  })

  it('changes the theme and the language', async () => {
    const { user, input } = await openPalette('user')

    await user.type(input, 'luminoasa')
    await user.keyboard('{Enter}')
    expect(document.documentElement).not.toHaveClass('dark')

    await user.keyboard('{Control>}k{/Control}')
    await user.type(await screen.findByRole('combobox'), 'engleza')
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('button', { name: /Search or jump to/ })).toBeInTheDocument()
  })
})

describe('sidebar', () => {
  it('counts the last 24 hours of incidents beside the security events', async () => {
    server.use(
      http.get('/api/security/summary', () =>
        HttpResponse.json(makeSummary({ last_24h: { info: 77, warn: 229, incident: 11 } })),
      ),
    )
    signedInAs(makeUser('admin'))
    renderApp('/org/audit')

    const link = await screen.findByRole('link', { name: /Evenimente de securitate/ })
    await waitFor(() => expect(link).toHaveTextContent('11'))
    expect(within(link).getByText('11 incidente în ultimele 24 de ore')).toHaveClass('sr-only')
  })

  it('shows no badge without incidents, and does not load the counts on personal pages', async () => {
    let summaries = 0
    server.use(
      http.get('/api/security/summary', () => {
        summaries += 1
        return HttpResponse.json(makeSummary({ last_24h: { info: 3, warn: 1, incident: 0 } }))
      }),
    )
    signedInAs(makeUser('admin'))
    renderApp('/me/sessions')

    await screen.findByRole('heading', { name: 'Sesiunile mele' })
    expect(summaries).toBe(0)
    const organization = screen.getByRole('navigation', { name: 'Acme' })
    await userEvent.setup().click(within(organization).getByRole('link', { name: 'Prezentare' }))
    await waitFor(() => expect(summaries).toBeGreaterThan(0))
    expect(within(organization).getByRole('link', { name: /Evenimente de securitate/ })).toHaveTextContent(
      /^Evenimente de securitate$/,
    )
  })

  it("groups the organization's pages and the account's, the current one marked", async () => {
    signedInAs(makeUser('admin'))
    renderApp('/org/users')

    expect(await screen.findByRole('heading', { level: 1, name: 'Utilizatori' })).toBeInTheDocument()
    const organization = screen.getByRole('navigation', { name: 'Acme' })
    expect(within(organization).getByRole('link', { name: 'Utilizatori' })).toHaveAttribute('aria-current', 'page')
    const account = screen.getByRole('navigation', { name: 'Contul meu' })
    expect(within(account).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Prezentare',
      'Sesiunile mele',
      'Activitatea mea',
    ])
    // No page numbers and no "Acme / 04" trail above the title.
    expect(screen.queryByText(/\/ 0\d/)).not.toBeInTheDocument()
  })

  it('places an account page under Users', async () => {
    signedInAs(makeUser('admin'))
    renderApp('/org/users/7')

    await screen.findByRole('heading', { level: 1, name: 'elena.radu' })
    const organization = screen.getByRole('navigation', { name: 'Acme' })
    expect(within(organization).getByRole('link', { name: 'Utilizatori' })).toHaveAttribute('aria-current', 'page')
  })
})
