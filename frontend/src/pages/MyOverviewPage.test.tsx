import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { ActivityEvent } from '@/features/account/api'
import { renderApp } from '@/test/render'
import { makeEvent, makeSession, makeUser, page, server, signedInAs } from '@/test/server'

const twoHoursAgo = () => new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()

interface Answers {
  logins?: ActivityEvent[]
  alerts?: ActivityEvent[]
  alertsCursor?: number | null
}

/** Answers the overview's two activity queries and records the alert query. */
function serveSummary({ logins = [], alerts = [], alertsCursor = null }: Answers) {
  const alertQueries: URLSearchParams[] = []
  server.use(
    http.get('/api/users/me/activity', ({ request }) => {
      const params = new URL(request.url).searchParams
      if (params.has('severity')) {
        alertQueries.push(params)
        return HttpResponse.json(page(alerts, alertsCursor))
      }
      return HttpResponse.json(page(logins))
    }),
  )
  return alertQueries
}

function stat(label: string) {
  const term = screen.getByText(label, { selector: 'dt' })
  return term.nextElementSibling as HTMLElement
}

describe('my overview page', () => {
  it('summarizes sessions, the previous sign-in and recent alerts', async () => {
    signedInAs(makeUser())
    server.use(
      http.get('/api/users/me/sessions', () =>
        HttpResponse.json([makeSession(), makeSession({ id: 'other', current: false })]),
      ),
    )
    const alertQueries = serveSummary({
      logins: [
        makeEvent({ id: 9 }),
        makeEvent({ id: 5, created_at: twoHoursAgo(), ip_address: '198.51.100.7' }),
      ],
      alerts: [makeEvent({ id: 8, event_type: 'login_failed', severity: 'warn' })],
    })
    renderApp('/me')

    const alertsTable = await screen.findByRole('table', { name: 'Evenimente' })

    expect(stat('Sesiuni active')).toHaveTextContent('2')
    expect(within(stat('Sesiuni active')).getByRole('link', { name: 'Gestionează sesiunile' })).toHaveAttribute(
      'href',
      '/me/sessions',
    )
    expect(stat('Autentificarea anterioară')).toHaveTextContent('acum 2 ore')
    expect(stat('Autentificarea anterioară')).toHaveTextContent('198.51.100.7')
    expect(stat('Alerte, ultimele 30 de zile')).toHaveTextContent('1')
    expect(alertsTable).toHaveTextContent('Încercare de autentificare eșuată')
    expect(screen.getByRole('link', { name: 'Vezi toate alertele' })).toHaveAttribute(
      'href',
      '/me/activity?filter=alerts',
    )

    // Alerts are counted over the last 30 days.
    const since = new Date(alertQueries[0].get('since') ?? '')
    const days = (Date.now() - since.getTime()) / (24 * 60 * 60 * 1000)
    expect(days).toBeCloseTo(30, 1)
  })

  it('says so when this is the first sign-in and nothing needs attention', async () => {
    signedInAs(makeUser())
    serveSummary({ logins: [makeEvent()] })
    renderApp('/me')

    expect(await screen.findByText('Nicio alertă în ultimele 30 de zile.')).toBeInTheDocument()
    expect(stat('Autentificarea anterioară')).toHaveTextContent('Aceasta este prima ta autentificare.')
    expect(stat('Alerte, ultimele 30 de zile')).toHaveTextContent('0')
  })

  it('shows that there are more alerts than one page holds', async () => {
    signedInAs(makeUser())
    const alerts = Array.from({ length: 50 }, (_, index) =>
      makeEvent({ id: 200 - index, event_type: 'login_failed', severity: 'warn' }),
    )
    serveSummary({ alerts, alertsCursor: 151 })
    renderApp('/me')

    const table = await screen.findByRole('table', { name: 'Evenimente' })

    expect(stat('Alerte, ultimele 30 de zile')).toHaveTextContent('50+')
    // Only the newest few are listed here.
    expect(within(table).getAllByRole('row')).toHaveLength(6)
  })

  it('keeps the rest of the page when one summary fails', async () => {
    signedInAs(makeUser())
    serveSummary({})
    server.use(
      http.get('/api/users/me/sessions', () =>
        HttpResponse.json({ detail: 'Internal error' }, { status: 500 }),
      ),
    )
    renderApp('/me')

    expect(await screen.findByText('Indisponibil')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bun venit, elena.radu' })).toBeInTheDocument()
    expect(stat('Alerte, ultimele 30 de zile')).toHaveTextContent('0')
  })
})
