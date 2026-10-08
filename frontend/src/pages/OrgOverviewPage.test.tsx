import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { SecurityEvent, SecuritySummary } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeSecurityEvent, makeSummary, makeUser, page, server, signedInAs } from '@/test/server'

const DAY = 24 * 60 * 60_000

const bruteForce = makeSecurityEvent({
  id: 501,
  event_type: 'brute_force_detected',
  severity: 'incident',
  user_id: 12,
  email: 'mihai.pop@example.com',
  ip_address: '203.0.113.9',
  message: 'Login locked for email: mihai.pop@example.com',
})
const lock = makeSecurityEvent({
  id: 502,
  event_type: 'account_locked',
  severity: 'incident',
  user_id: 3,
  target_user_id: 12,
  email: 'ioana.sec@example.com',
  ip_address: '192.0.2.44',
  message: 'Security analyst locked user_id=12 for 24 hour(s)',
})

/** Answers the summary and the incident list, counting the requests. */
function serve(summary: Partial<SecuritySummary> = {}, incidents: SecurityEvent[] = []) {
  const requests = { summary: 0, incidents: [] as URLSearchParams[] }
  server.use(
    http.get('/api/security/summary', () => {
      requests.summary += 1
      return HttpResponse.json(makeSummary(summary))
    }),
    http.get('/api/security/events', ({ request }) => {
      requests.incidents.push(new URL(request.url).searchParams)
      return HttpResponse.json(page(incidents))
    }),
  )
  return requests
}

async function openOverview() {
  signedInAs(makeUser('security_analyst'))
  const result = renderApp('/org')
  await screen.findByRole('heading', { name: 'Prezentarea organizației' })
  return result
}

describe('organization overview', () => {
  it('shows the last 24 hours beside the last 7 days, each count opening its records', async () => {
    serve({
      last_24h: { info: 12, warn: 4, incident: 1 },
      last_7d: { info: 80, warn: 20, incident: 3 },
      failed_logins_24h: 41,
      locked_logins: 1,
      users_total: 25,
      users_inactive: 2,
      accounts_locked: 1,
    })
    await openOverview()

    const summary = await screen.findByRole('list', { name: 'Rezumatul securității' })
    const tile = (name: RegExp) => within(summary).getByRole('link', { name })

    expect(tile(/^Incidente/)).toHaveTextContent('Incidente1în 24 de ore3 în 7 zile')
    expect(tile(/^Incidente/)).toHaveAttribute('href', '/org/events?range=24h&severity=incident')
    expect(tile(/^Avertismente/)).toHaveTextContent('Avertismente4în 24 de ore20 în 7 zile')
    expect(tile(/^Avertismente/)).toHaveAttribute('href', '/org/events?range=24h&severity=warn')
    expect(tile(/^Evenimente informative/)).toHaveTextContent('Evenimente informative12în 24 de ore80 în 7 zile')

    expect(tile(/^Autentificări eșuate/)).toHaveTextContent('1 adresă de email blocată acum')
    expect(tile(/^Autentificări eșuate/)).toHaveTextContent('41')
    expect(tile(/^Autentificări eșuate/)).toHaveAttribute(
      'href',
      '/org/events?range=24h&type=login_failed',
    )
    expect(tile(/^Conturi blocate/)).toHaveAttribute('href', '/org/users?state=locked')
    expect(tile(/^Conturi dezactivate/)).toHaveTextContent('2din 25 de conturi')
    expect(tile(/^Conturi dezactivate/)).toHaveAttribute('href', '/org/users?state=inactive')
  })

  it('lists the newest incidents of the last 7 days and opens their details', async () => {
    const user = userEvent.setup()
    const requests = serve({}, [lock, bruteForce])
    await openOverview()

    const table = await screen.findByRole('table', { name: 'Ultimele incidente' })
    const [first, second] = within(table).getAllByRole('row').slice(1)
    expect(first).toHaveTextContent('Cont blocat temporar')
    expect(first).toHaveTextContent('ioana.sec@example.com')
    expect(second).toHaveTextContent('Forță brută detectată, autentificare blocată')
    expect(second).toHaveTextContent('203.0.113.9')

    const [params] = requests.incidents
    expect(params.getAll('severity')).toEqual(['incident'])
    expect(params.get('limit')).toBe('5')
    const since = Date.parse(params.get('since') ?? '')
    expect(Math.abs(Date.now() - 7 * DAY - since)).toBeLessThan(60_000)

    expect(screen.getByRole('link', { name: 'Vezi toate incidentele' })).toHaveAttribute(
      'href',
      '/org/events?severity=incident',
    )

    await user.click(within(first).getByRole('button', { name: 'Cont blocat temporar' }))
    const details = await screen.findByRole('dialog', { name: 'Cont blocat temporar' })
    expect(details).toHaveTextContent('Security analyst locked user_id=12 for 24 hour(s)')
    expect(within(details).getByRole('link', { name: 'Deschide contul' })).toHaveAttribute(
      'href',
      '/org/users/3',
    )
    expect(within(details).getByRole('link', { name: 'Deschide ținta' })).toHaveAttribute(
      'href',
      '/org/users/12',
    )
  })

  it('ranks the sources of failed sign-ins and links each to its attempts', async () => {
    serve({
      failed_logins_24h: 28,
      top_failed_login_sources: [
        { ip_address: '203.0.113.9', failed_logins: 20 },
        { ip_address: '198.51.100.4', failed_logins: 5 },
      ],
    })
    await openOverview()

    const sources = await screen.findByRole('list', { name: 'Surse de autentificări eșuate' })
    const [first, second] = within(sources).getAllByRole('link')
    expect(first).toHaveAccessibleName('203.0.113.9: 20 de autentificări eșuate')
    expect(first).toHaveAttribute('href', '/org/events?range=24h&type=login_failed&q=203.0.113.9')
    expect(second).toHaveAccessibleName('198.51.100.4: 5 autentificări eșuate')

    // Bars are scaled to the largest source.
    const bar = (link: HTMLElement) => link.querySelector<HTMLElement>('[style]')
    expect(bar(first)).toHaveStyle({ width: '100%' })
    expect(bar(second)).toHaveStyle({ width: '25%' })
  })

  it('says when there is nothing to show', async () => {
    serve()
    await openOverview()

    expect(await screen.findByText('Niciun incident în ultimele 7 zile.')).toBeInTheDocument()
    expect(screen.getByText('Nicio autentificare eșuată în ultimele 24 de ore.')).toBeInTheDocument()
    // The full list stays one click away even when nothing is recent.
    expect(screen.getByRole('link', { name: 'Vezi toate incidentele' })).toBeInTheDocument()
  })

  it('keeps the incidents when the counts fail, and retries the counts', async () => {
    const user = userEvent.setup()
    serve({}, [bruteForce])
    server.use(
      http.get('/api/security/summary', () => HttpResponse.json({ detail: 'down' }, { status: 503 })),
    )
    await openOverview()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Serverul nu a răspuns.')
    expect(screen.getByRole('table', { name: 'Ultimele incidente' })).toBeInTheDocument()
    expect(screen.getByText('Indisponibil.')).toBeInTheDocument()

    server.use(
      http.get('/api/security/summary', () =>
        HttpResponse.json(makeSummary({ last_24h: { info: 0, warn: 0, incident: 2 } })),
      ),
    )
    await user.click(within(alert).getByRole('button', { name: 'Încearcă din nou' }))

    const summary = await screen.findByRole('list', { name: 'Rezumatul securității' })
    expect(within(summary).getByRole('link', { name: /^Incidente/ })).toHaveTextContent('Incidente2')
  })

  it('refreshes the counts and the incidents together', async () => {
    const user = userEvent.setup()
    const requests = serve({}, [bruteForce])
    await openOverview()
    await screen.findByRole('table', { name: 'Ultimele incidente' })
    await screen.findByText(/^Actualizat/)
    expect(requests.summary).toBe(1)
    expect(requests.incidents).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Reîmprospătează' }))

    await waitFor(() => {
      expect(requests.summary).toBe(2)
      expect(requests.incidents).toHaveLength(2)
    })
  })
})
