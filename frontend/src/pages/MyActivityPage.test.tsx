import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { ActivityEvent } from '@/features/account/api'
import { renderApp } from '@/test/render'
import { makeEvent, makeUser, page, server, signedInAs } from '@/test/server'

const failed = makeEvent({ id: 103, event_type: 'login_failed', severity: 'warn', ip_address: '203.0.113.9' })
const locked = makeEvent({ id: 102, event_type: 'brute_force_detected', severity: 'incident', ip_address: '203.0.113.9' })
const login = makeEvent({ id: 101 })
const registered = makeEvent({ id: 1, event_type: 'user_registered', ip_address: null })

/** Answers each activity request with `respond` and records its query. */
function serveActivity(respond: (params: URLSearchParams) => ActivityEvent[] | [ActivityEvent[], number]) {
  const requests: URLSearchParams[] = []
  server.use(
    http.get('/api/users/me/activity', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(params)
      const result = respond(params)
      const [items, cursor] = Array.isArray(result[0]) ? result : [result, null]
      return HttpResponse.json(page(items as ActivityEvent[], cursor as number | null))
    }),
  )
  return requests
}

function rowTexts() {
  const table = screen.getByRole('table', { name: 'Evenimente' })
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => row.textContent)
}

describe('my activity page', () => {
  it('describes each event in the interface language', async () => {
    signedInAs(makeUser())
    serveActivity(() => [failed, locked, login])
    renderApp('/me/activity')

    const table = await screen.findByRole('table', { name: 'Evenimente' })
    const rows = within(table).getAllByRole('row')

    expect(rows[1]).toHaveTextContent('Încercare de autentificare eșuată')
    expect(rows[1]).toHaveTextContent('Avertisment')
    expect(rows[1]).toHaveTextContent('203.0.113.9')
    expect(rows[2]).toHaveTextContent('Autentificare blocată temporar')
    expect(rows[2]).toHaveTextContent('Incident')
    expect(rows[3]).toHaveTextContent('Autentificare reușită')
    expect(rows[3]).toHaveTextContent('Informativ')
    expect(within(rows[3]).getByText(/2026/)).toHaveAttribute('datetime', login.created_at)
  })

  it('tells actions taken on the account apart from actions taken by it', async () => {
    signedInAs(makeUser('admin'))
    serveActivity(() => [
      makeEvent({ id: 202, event_type: 'user_role_changed', as_target: true, ip_address: null }),
      makeEvent({ id: 201, event_type: 'user_role_changed' }),
      makeEvent({ id: 200, event_type: 'user_sessions_revoked', as_target: true, ip_address: null }),
      makeEvent({ id: 199, event_type: 'account_locked', as_target: true, ip_address: null }),
      makeEvent({
        id: 198,
        event_type: 'privileged_role_granted',
        severity: 'warn',
        as_target: true,
        ip_address: null,
      }),
      makeEvent({ id: 197, event_type: 'privileged_role_granted', severity: 'warn' }),
      makeEvent({ id: 196, event_type: 'dormant_account_login', severity: 'warn' }),
      makeEvent({ id: 195, event_type: 'unfamiliar_sign_in', severity: 'warn' }),
    ])
    renderApp('/me/activity')

    await screen.findByRole('table', { name: 'Evenimente' })

    expect(rowTexts()).toEqual([
      expect.stringContaining('Rolul tău a fost schimbat'),
      expect.stringContaining('Ai schimbat rolul unui utilizator'),
      expect.stringContaining('Un administrator ți-a închis sesiunile'),
      expect.stringContaining('Contul tău a fost blocat temporar'),
      expect.stringContaining('Ai primit un rol privilegiat'),
      expect.stringContaining('Ai acordat un rol privilegiat'),
      expect.stringContaining('Autentificare după o perioadă lungă de inactivitate'),
      expect.stringContaining('Autentificare dintr-o rețea nouă, de pe un dispozitiv nou'),
    ])
    expect(rowTexts()[0]).toContain('—')
  })

  it('shows only alerts when asked, and keeps the choice in the address', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    const requests = serveActivity((params) =>
      params.has('severity') ? [failed, locked] : [failed, locked, login],
    )
    const { router } = renderApp('/me/activity')

    await screen.findByRole('table', { name: 'Evenimente' })
    await user.click(screen.getByRole('button', { name: 'Doar alerte' }))

    expect(await screen.findAllByRole('row')).toHaveLength(3)
    expect(router.state.location.search).toBe('?filter=alerts')
    expect(screen.getByRole('button', { name: 'Doar alerte' })).toHaveAttribute('aria-pressed', 'true')
    expect(requests.at(-1)?.getAll('severity')).toEqual(['warn', 'incident'])
    expect(requests[0].has('severity')).toBe(false)
  })

  it('opens directly on alerts from a link', async () => {
    signedInAs(makeUser())
    const requests = serveActivity(() => [failed])
    renderApp('/me/activity?filter=alerts')

    await screen.findByRole('table', { name: 'Evenimente' })

    expect(requests[0].getAll('severity')).toEqual(['warn', 'incident'])
  })

  it('ignores an unknown filter in the address', async () => {
    signedInAs(makeUser())
    const requests = serveActivity(() => [login])
    renderApp('/me/activity?filter=everything')

    await screen.findByRole('table', { name: 'Evenimente' })

    expect(requests[0].has('severity')).toBe(false)
    expect(screen.getByRole('button', { name: 'Tot' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('loads older events with the cursor of the previous page', async () => {
    const user = userEvent.setup()
    signedInAs(makeUser())
    const requests = serveActivity((params) =>
      params.get('before_id') === '102' ? [login, registered] : [[failed, locked], 102],
    )
    renderApp('/me/activity')

    await screen.findByRole('table', { name: 'Evenimente' })
    expect(screen.queryByText('Ai ajuns la începutul istoricului.')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Încarcă mai multe' }))

    expect(await screen.findByText('Ai ajuns la începutul istoricului.')).toBeInTheDocument()
    expect(rowTexts()).toHaveLength(4)
    expect(rowTexts()[3]).toContain('Cont creat')
    expect(requests.map((params) => params.get('before_id'))).toEqual([null, '102'])
  })

  it('reassures when there are no alerts', async () => {
    signedInAs(makeUser())
    serveActivity(() => [])
    renderApp('/me/activity?filter=alerts')

    expect(
      await screen.findByText('Nicio alertă. Nu au existat încercări suspecte asupra contului tău.'),
    ).toBeInTheDocument()
  })
})
