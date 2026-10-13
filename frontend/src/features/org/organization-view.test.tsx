import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, type JsonBodyType } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import {
  makeOrganization,
  makeSecurityEvent,
  makeSummary,
  makeUser,
  page,
  server,
  signedInAs,
} from '@/test/server'

const ORGANIZATIONS = [
  makeOrganization({ id: 1, name: 'Acme', slug: 'acme' }),
  makeOrganization({ id: 2, name: 'Globex', slug: 'globex' }),
  makeOrganization({ id: 3, name: 'Initech', slug: 'initech', suspended_at: '2026-10-10T08:00:00Z' }),
]

/** The organization each request to `path` named, in order: null for none. */
function recordOrganizations(path: string, answer: () => JsonBodyType) {
  const named: (string | null)[] = []
  server.use(
    http.get(path, ({ request }) => {
      named.push(new URL(request.url).searchParams.get('organization_id'))
      return HttpResponse.json(answer())
    }),
  )
  return named
}

function serveOrganizations() {
  server.use(http.get('/api/admin/organizations', () => HttpResponse.json(ORGANIZATIONS)))
}

const events = () =>
  page([
    makeSecurityEvent({ id: 2, organization_id: 1, email: 'ada@acme.example' }),
    makeSecurityEvent({ id: 1, organization_id: null, email: 'nobody@example.com' }),
  ])

describe('the owner’s choice of organization', () => {
  it('shows every organization with a column, then one without it', async () => {
    serveOrganizations()
    const named = recordOrganizations('/api/security/events', events)
    const summaries = recordOrganizations('/api/security/summary', () => makeSummary())
    signedInAs(makeUser('owner', { id: 1 }))
    const { router } = renderApp('/org/events')
    const user = userEvent.setup()

    const table = await screen.findByRole('table', { name: 'Evenimente de securitate' })
    expect(within(table).getByRole('columnheader', { name: 'Organizație' })).toBeInTheDocument()
    expect(await within(table).findByRole('cell', { name: 'Acme' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: 'Platformă' })).toBeInTheDocument()
    expect(named).toEqual([null])

    const picker = screen.getByLabelText('Organizația afișată')
    expect(within(picker).getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Toate organizațiile',
      'Acme',
      'Globex',
      'Initech (suspendată)',
    ])
    await user.selectOptions(picker, 'Acme')

    await waitFor(() => expect(named.at(-1)).toBe('1'))
    expect(router.state.location.search).toBe('?org=1')
    // The band and the incident badge follow the choice too.
    await waitFor(() => expect(summaries.at(-1)).toBe('1'))
    // Whichever table is shown now has its rows but no organization column.
    await waitFor(() => {
      const shown = screen.getByRole('table', { name: 'Evenimente de securitate' })
      expect(within(shown).getAllByRole('row')).toHaveLength(3)
      expect(within(shown).queryByRole('columnheader', { name: 'Organizație' })).not.toBeInTheDocument()
    })

    await user.selectOptions(picker, 'Toate organizațiile')
    await waitFor(() => expect(named.at(-1)).toBeNull())
    expect(router.state.location.search).toBe('?org=all')
  })

  it('keeps the choice when a filter or a link drops it from the address', async () => {
    serveOrganizations()
    const named = recordOrganizations('/api/security/events', events)
    const users = recordOrganizations('/api/admin/users', () => page([]))
    signedInAs(makeUser('owner', { id: 1 }))
    const { router } = renderApp('/org/events?org=2')
    const user = userEvent.setup()

    await screen.findByRole('table', { name: 'Evenimente de securitate' })
    await user.click(screen.getByRole('button', { name: 'Incident' }))
    await waitFor(() => expect(router.state.location.search).toBe('?severity=incident&org=2'))

    const nav = screen.getByRole('navigation', { name: 'Navigare principală' })
    await user.click(within(nav).getByRole('link', { name: /Utilizatori/ }))
    await waitFor(() => expect(router.state.location.search).toBe('?org=2'))
    expect(router.state.location.pathname).toBe('/org/users')

    // Not one load of every organization in between: each would be audited.
    expect(named.length).toBeGreaterThan(1)
    expect(new Set(named)).toEqual(new Set(['2']))
    await waitFor(() => expect(users).not.toHaveLength(0))
    expect(new Set(users)).toEqual(new Set(['2']))
  })

  it('falls back to every organization when the address names an unknown one', async () => {
    serveOrganizations()
    const named = recordOrganizations('/api/security/events', events)
    signedInAs(makeUser('owner', { id: 1 }))
    const { router } = renderApp('/org/events?org=99')

    await waitFor(() => expect(router.state.location.search).toBe('?org=all'))
    await waitFor(() => expect(named.at(-1)).toBeNull())
    expect(screen.getByLabelText('Organizația afișată')).toHaveValue('')
  })

  it('opens one organization from the platform overview', async () => {
    serveOrganizations()
    const summaries: (string | null)[] = []
    server.use(
      http.get('/api/security/summary', ({ request }) => {
        const organization = new URL(request.url).searchParams.get('organization_id')
        summaries.push(organization)
        return HttpResponse.json(
          makeSummary({
            organizations:
              organization === null
                ? [
                    {
                      id: 2,
                      name: 'Globex',
                      slug: 'globex',
                      suspended: false,
                      threat_level: 'incident',
                      last_24h: { info: 4, warn: 2, incident: 1 },
                    },
                    {
                      id: null,
                      name: null,
                      slug: null,
                      suspended: false,
                      threat_level: 'calm',
                      last_24h: { info: 9, warn: 1, incident: 0 },
                    },
                    {
                      id: 3,
                      name: 'Initech',
                      slug: 'initech',
                      suspended: true,
                      threat_level: 'calm',
                      last_24h: { info: 0, warn: 0, incident: 0 },
                    },
                  ]
                : null,
          }),
        )
      }),
    )
    signedInAs(makeUser('owner', { id: 1 }))
    renderApp('/org')
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { level: 1, name: 'Prezentarea platformei' })).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Organizații după nivel' })
    const [globex, platform, initech] = within(table).getAllByRole('row').slice(1)
    expect(globex).toHaveTextContent('Incident activ')
    expect(globex).toHaveTextContent('1')
    expect(platform).toHaveTextContent('Platformă')
    expect(within(platform).queryByRole('button')).not.toBeInTheDocument()
    expect(initech).toHaveTextContent('Suspendată')
    expect(initech).toHaveTextContent('Calm')

    await user.click(within(globex).getByRole('button', { name: 'Arată doar Globex' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Prezentarea organizației' })).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Organizații după nivel' })).not.toBeInTheDocument()
    expect(summaries.at(-1)).toBe('2')
    expect(screen.getByLabelText('Organizația afișată')).toHaveValue('2')
  })
})

describe('a member', () => {
  it('sees their organization’s name, no picker, and never names an organization', async () => {
    const named = recordOrganizations('/api/security/events', events)
    const summaries = recordOrganizations('/api/security/summary', () => makeSummary())
    let listed = 0
    server.use(
      http.get('/api/admin/organizations', () => {
        listed += 1
        return HttpResponse.json(ORGANIZATIONS)
      }),
    )
    signedInAs(makeUser('admin'))
    // Even with an organization in the address: only the owner may name one.
    const { router } = renderApp('/org/events?org=2')

    const table = await screen.findByRole('table', { name: 'Evenimente de securitate' })
    expect(within(table).queryByRole('columnheader', { name: 'Organizație' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Organizația afișată')).not.toBeInTheDocument()
    expect(screen.getByText('Acme / 02 Evenimente de securitate')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Meniul contului' })).toHaveTextContent('Administrator · Acme')
    await waitFor(() => expect(summaries).not.toHaveLength(0))
    expect([...named, ...summaries].every((organization) => organization === null)).toBe(true)
    expect(listed).toBe(0)
    expect(router.state.location.search).toBe('?org=2')
  })
})
