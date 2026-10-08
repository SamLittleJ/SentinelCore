import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { User } from '@/features/auth/api'
import { renderApp } from '@/test/render'
import { makeUser, page, server, signedInAs } from '@/test/server'

const HOUR = 60 * 60_000

const mihai = makeUser('user', {
  id: 12,
  username: 'mihai.pop',
  email: 'mihai.pop@example.com',
  created_at: '2026-09-01T10:00:00Z',
})
const lockedAnalyst = makeUser('security_analyst', {
  id: 11,
  username: 'ioana.sec',
  email: 'ioana.sec@example.com',
  locked_until: new Date(Date.now() + 5 * HOUR).toISOString(),
})
const deactivatedAdmin = makeUser('admin', {
  id: 10,
  username: 'radu.admin',
  email: 'radu.admin@example.com',
  is_active: false,
  // A lock that has already expired is not shown.
  locked_until: new Date(Date.now() - HOUR).toISOString(),
})

/** Answers each user list request with `respond` and records its query. */
function serveUsers(respond: (params: URLSearchParams) => User[] | [User[], number]) {
  const requests: URLSearchParams[] = []
  server.use(
    http.get('/api/admin/users', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(params)
      const result = respond(params)
      const [items, cursor] = Array.isArray(result[0]) ? result : [result, null]
      return HttpResponse.json(page(items as User[], cursor as number | null))
    }),
  )
  return requests
}

async function openUsers(path = '/org/users') {
  signedInAs(makeUser('security_analyst'))
  const result = renderApp(path)
  const table = await screen.findByRole('table', { name: 'Utilizatori' })
  return { ...result, table }
}

function rows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('organization users page', () => {
  it('lists accounts with their role and whether they can sign in', async () => {
    serveUsers(() => [mihai, lockedAnalyst, deactivatedAdmin])
    const { table } = await openUsers()

    const [first, second, third] = rows(table)
    expect(first).toHaveTextContent('mihai.pop')
    expect(first).toHaveTextContent('mihai.pop@example.com')
    expect(first).toHaveTextContent('Utilizator')
    expect(first).toHaveTextContent('Activ')
    expect(second).toHaveTextContent('Analist de securitate')
    expect(second).toHaveTextContent('Blocat')
    expect(second).not.toHaveTextContent('Activ')
    expect(third).toHaveTextContent('Administrator')
    expect(third).toHaveTextContent('Dezactivat')
    expect(third).not.toHaveTextContent('Blocat')
  })

  it('searches, filters by role and state, and keeps the filters in the address', async () => {
    const user = userEvent.setup()
    const requests = serveUsers(() => [mihai])
    const { router } = await openUsers()

    const input = screen.getByLabelText('Nume de utilizator sau email')
    await user.type(input, 'MIH{Enter}')
    expect(requests.at(-1)?.get('q')).toBe('MIH')
    expect(input).toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Roluri' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Administrator' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Proprietar' }))
    await user.keyboard('{Escape}')
    expect(requests.at(-1)?.getAll('role')).toEqual(['admin', 'owner'])
    expect(screen.getByRole('button', { name: 'Roluri' })).toHaveTextContent('2 roluri')

    await user.click(screen.getByRole('button', { name: 'Blocate' }))
    expect(requests.at(-1)?.get('locked')).toBe('true')
    expect(requests.at(-1)?.has('is_active')).toBe(false)
    expect(router.state.location.search).toBe('?q=MIH&role=admin&role=owner&state=locked')
  })

  it('asks for accounts that can sign in as active and not locked', async () => {
    const user = userEvent.setup()
    const requests = serveUsers(() => [mihai])
    await openUsers()

    await user.click(screen.getByRole('button', { name: 'Active' }))
    expect(requests.at(-1)?.get('is_active')).toBe('true')
    expect(requests.at(-1)?.get('locked')).toBe('false')

    await user.click(screen.getByRole('button', { name: 'Dezactivate' }))
    expect(requests.at(-1)?.get('is_active')).toBe('false')
    expect(requests.at(-1)?.has('locked')).toBe(false)
  })

  it('reads filters from a shared link and ignores invalid values', async () => {
    const requests = serveUsers(() => [mihai])
    await openUsers('/org/users?q=pop&role=admin&role=superuser&state=gone')

    expect(requests[0].get('q')).toBe('pop')
    expect(requests[0].getAll('role')).toEqual(['admin'])
    expect(requests[0].has('locked')).toBe(false)
    expect(requests[0].has('is_active')).toBe(false)
    expect(screen.getByRole('button', { name: 'Toate', pressed: true })).toBeInTheDocument()
  })

  it('resets the filters', async () => {
    const user = userEvent.setup()
    serveUsers(() => [mihai])
    const { router } = await openUsers('/org/users?q=pop&state=inactive')

    await user.click(screen.getByRole('button', { name: 'Resetează filtrele' }))

    expect(router.state.location.search).toBe('')
    expect(screen.getByLabelText('Nume de utilizator sau email')).toHaveValue('')
  })

  it('says when no account matches the filters', async () => {
    serveUsers(() => [])
    signedInAs(makeUser('admin'))
    renderApp('/org/users?state=locked')

    expect(await screen.findByText('Niciun utilizator pentru filtrele alese.')).toBeInTheDocument()
  })

  it('opens an account from its row and goes back to the filtered list', async () => {
    const user = userEvent.setup()
    serveUsers(() => [mihai])
    server.use(http.get('/api/admin/users/12', () => HttpResponse.json(mihai)))
    const { table, router } = await openUsers('/org/users?state=active')

    // A click anywhere on the row opens the account.
    await user.click(within(rows(table)[0]).getByText('Utilizator'))
    await screen.findByRole('heading', { name: 'mihai.pop', level: 1 })
    expect(router.state.location.pathname).toBe('/org/users/12')

    await user.click(screen.getByRole('link', { name: 'Înapoi la utilizatori' }))
    expect(router.state.location.pathname).toBe('/org/users')
    expect(router.state.location.search).toBe('?state=active')
  })

  it('loads more accounts with the cursor', async () => {
    const user = userEvent.setup()
    const requests = serveUsers((params) =>
      params.get('before_id') === '11' ? [deactivatedAdmin] : [[mihai, lockedAnalyst], 11],
    )
    const { table } = await openUsers()

    await user.click(screen.getByRole('button', { name: 'Încarcă mai multe' }))

    await screen.findByText('Acestea sunt toate conturile.')
    expect(rows(table)).toHaveLength(3)
    expect(requests[1].get('before_id')).toBe('11')
  })
})
