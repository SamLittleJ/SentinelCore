import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Session } from '@/features/account/api'
import { renderApp } from '@/test/render'
import { makeSession, makeUser, server, signedInAs } from '@/test/server'

const PHONE =
  'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'

const current = makeSession()
const phone = makeSession({
  id: 'phone-session',
  current: false,
  ip_address: '198.51.100.7',
  user_agent: PHONE,
})
const script = makeSession({
  id: 'script-session',
  current: false,
  ip_address: null,
  user_agent: 'python-httpx/0.28.1',
})

/** Serves `sessions` from a list that DELETE requests really shrink. */
function serveSessions(initial: Session[]) {
  let sessions = [...initial]
  const deleted: string[] = []
  server.use(
    http.get('/api/users/me/sessions', () => HttpResponse.json(sessions)),
    http.delete('/api/users/me/sessions/:id', ({ params }) => {
      deleted.push(String(params.id))
      sessions = sessions.filter((session) => session.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete('/api/users/me/sessions', () => {
      const revoked = sessions.filter((session) => !session.current).length
      sessions = sessions.filter((session) => session.current)
      deleted.push('others')
      return HttpResponse.json({ revoked_sessions: revoked })
    }),
  )
  return deleted
}

async function sessionRows() {
  const list = await screen.findByRole('list', { name: 'Sesiuni active' })
  return within(list).getAllByRole('listitem')
}

describe('my sessions page', () => {
  it('lists this browser first, then the other devices', async () => {
    signedInAs(makeUser())
    // The API orders newest first, so this browser is not necessarily first.
    serveSessions([phone, current, script])
    renderApp('/me/sessions')

    const rows = await sessionRows()

    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Firefox pe Linux')
    expect(rows[0]).toHaveTextContent('Această sesiune')
    expect(rows[0]).toHaveTextContent('acum 5 minute')
    expect(rows[0]).toHaveTextContent('peste 25 de minute')
    expect(rows[1]).toHaveTextContent('Chrome pe Android')
    expect(rows[1]).toHaveTextContent('198.51.100.7')
    expect(rows[2]).toHaveTextContent('Dispozitiv necunoscut')
    expect(rows[2]).toHaveTextContent('necunoscută')
  })

  it('ends another session after confirmation', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    const deleted = serveSessions([current, phone])
    renderApp('/me/sessions')

    const [, phoneRow] = await sessionRows()
    await user.click(within(phoneRow).getByRole('button', { name: 'Închide sesiunea' }))
    expect(deleted).toEqual([])

    const confirm = within(phoneRow).getByRole('button', { name: 'Confirmă închiderea' })
    expect(confirm).toHaveAccessibleDescription('Chrome pe Android')
    await user.click(confirm)

    expect(await screen.findByRole('status')).toHaveTextContent('Sesiunea a fost închisă.')
    expect(deleted).toEqual(['phone-session'])
    expect(await sessionRows()).toHaveLength(1)
  })

  it('cancels without ending the session', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    const deleted = serveSessions([current, phone])
    renderApp('/me/sessions')

    const [, phoneRow] = await sessionRows()
    await user.click(within(phoneRow).getByRole('button', { name: 'Închide sesiunea' }))
    await user.click(within(phoneRow).getByRole('button', { name: 'Anulează' }))

    expect(deleted).toEqual([])
    expect(within(phoneRow).getByRole('button', { name: 'Închide sesiunea' })).toBeInTheDocument()
  })

  it('explains when the session had already ended', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    serveSessions([current, phone])
    server.use(
      http.delete('/api/users/me/sessions/:id', () =>
        HttpResponse.json({ detail: 'Session not found' }, { status: 404 }),
      ),
    )
    renderApp('/me/sessions')

    const [, phoneRow] = await sessionRows()
    await user.click(within(phoneRow).getByRole('button', { name: 'Închide sesiunea' }))
    await user.click(within(phoneRow).getByRole('button', { name: 'Confirmă închiderea' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Sesiunea nu mai era activă.')
  })

  it('reports a failed action', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    serveSessions([current, phone])
    server.use(
      http.delete('/api/users/me/sessions/:id', () =>
        HttpResponse.json({ detail: 'Internal error' }, { status: 500 }),
      ),
    )
    renderApp('/me/sessions')

    const [, phoneRow] = await sessionRows()
    await user.click(within(phoneRow).getByRole('button', { name: 'Închide sesiunea' }))
    await user.click(within(phoneRow).getByRole('button', { name: 'Confirmă închiderea' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Acțiunea nu a reușit.')
  })

  it('ends every other session at once', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    const deleted = serveSessions([current, phone, script])
    renderApp('/me/sessions')

    await sessionRows()
    await user.click(screen.getByRole('button', { name: 'Închide celelalte sesiuni' }))
    expect(screen.getByText(/Toate celelalte dispozitive vor fi deconectate/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Închide-le' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Am închis 2 sesiuni.')
    expect(deleted).toEqual(['others'])
    expect(await sessionRows()).toHaveLength(1)
  })

  it('has nothing to end when only this browser is signed in', async () => {
    signedInAs(makeUser())
    serveSessions([current])
    renderApp('/me/sessions')

    const [row] = await sessionRows()

    expect(screen.getByRole('button', { name: 'Închide celelalte sesiuni' })).toBeDisabled()
    expect(within(row).queryByRole('button', { name: 'Închide sesiunea' })).not.toBeInTheDocument()
  })

  it('signs out from this browser', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    serveSessions([current])
    let loggedOut = false
    server.use(
      http.post('/api/auth/logout', () => {
        loggedOut = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { router } = renderApp('/me/sessions')

    const [row] = await sessionRows()
    signedInAs(null)
    await user.click(within(row).getByRole('button', { name: 'Deconectează-te' }))

    expect(await screen.findByRole('heading', { name: 'Autentificare' })).toBeInTheDocument()
    expect(loggedOut).toBe(true)
    expect(router.state.location.pathname).toBe('/login')
  })

  it('offers a retry when the list does not load', async () => {
    signedInAs(makeUser())
    server.use(
      http.get('/api/users/me/sessions', () =>
        HttpResponse.json({ detail: 'Internal error' }, { status: 500 }),
      ),
    )
    renderApp('/me/sessions')

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByRole('button', { name: 'Încearcă din nou' })).toBeInTheDocument()
  })
})
