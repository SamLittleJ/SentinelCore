import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { SecurityEvent } from '@/features/org/api'
import { formatDateTime } from '@/lib/format'
import { renderApp } from '@/test/render'
import { makeSecurityEvent, makeUser, page, server, signedInAs } from '@/test/server'

const DAY = 24 * 60 * 60_000

const failed = makeSecurityEvent({ id: 503 })
const locked = makeSecurityEvent({
  id: 502,
  event_type: 'account_locked',
  severity: 'incident',
  user_id: 3,
  target_user_id: 4,
  email: 'ioana.sec@example.com',
  ip_address: '192.0.2.44',
  message: 'Security analyst locked user_id=4 for 24 hour(s). Reason: new country',
})
const signedIn = makeSecurityEvent({
  id: 501,
  event_type: 'login_success',
  severity: 'info',
  user_id: 4,
  email: 'mihai.pop@example.com',
  ip_address: null,
})

/** Answers each events request with `respond` and records its query. */
function serveEvents(
  respond: (params: URLSearchParams) => SecurityEvent[] | [SecurityEvent[], number] | Response,
) {
  const requests: URLSearchParams[] = []
  server.use(
    http.get('/api/security/events', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(params)
      const result = respond(params)
      if (result instanceof Response) return result
      const [items, cursor] = Array.isArray(result[0]) ? result : [result, null]
      return HttpResponse.json(page(items as SecurityEvent[], cursor as number | null))
    }),
  )
  return requests
}

async function openEvents(path = '/org/events') {
  signedInAs(makeUser('security_analyst'))
  const result = renderApp(path)
  const table = await screen.findByRole('table', { name: 'Evenimente de securitate' })
  return { ...result, table }
}

function rows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('organization security events page', () => {
  it('lists events with neutral descriptions, severity, account and address', async () => {
    serveEvents(() => [failed, locked, signedIn])
    const { table } = await openEvents()

    const [first, second, third] = rows(table)
    expect(first).toHaveTextContent('Autentificare eșuată')
    expect(first).toHaveTextContent('Avertisment')
    expect(first).toHaveTextContent('mihai.pop@example.com')
    expect(first).toHaveTextContent('203.0.113.9')
    expect(second).toHaveTextContent('Cont blocat temporar')
    expect(second).toHaveTextContent('Incident')
    expect(third).toHaveTextContent('Autentificare reușită')
    expect(third).toHaveTextContent('—')
  })

  it('asks for the last 7 days by default and for all time when chosen', async () => {
    const before = Date.now()
    const requests = serveEvents(() => [failed])
    const { router } = await openEvents()

    const since = Date.parse(requests[0].get('since') ?? '')
    expect(since).toBeGreaterThanOrEqual(before - 7 * DAY)
    expect(since).toBeLessThanOrEqual(Date.now() - 7 * DAY)

    await userEvent.setup().click(screen.getByRole('button', { name: 'Tot' }))

    expect(await screen.findByRole('button', { name: 'Tot', pressed: true })).toBeInTheDocument()
    expect(requests.at(-1)?.has('since')).toBe(false)
    expect(router.state.location.search).toBe('?range=all')
  })

  it('filters by severity and event type, and keeps them in the address', async () => {
    const user = userEvent.setup()
    const requests = serveEvents(() => [locked])
    const { router } = await openEvents()

    await user.click(screen.getByRole('button', { name: 'Incident' }))
    await user.click(screen.getByRole('button', { name: 'Tipuri de evenimente' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Cont blocat temporar' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Forță brută detectată, autentificare blocată' }))
    await user.keyboard('{Escape}')

    const last = requests.at(-1)
    expect(last?.getAll('severity')).toEqual(['incident'])
    expect(last?.getAll('event_type')).toEqual(['account_locked', 'brute_force_detected'])
    expect(router.state.location.search).toBe(
      '?type=account_locked&type=brute_force_detected&severity=incident',
    )
    expect(screen.getByRole('button', { name: 'Tipuri de evenimente' })).toHaveTextContent('2 tipuri')
  })

  it('reads filters from a shared link', async () => {
    const requests = serveEvents(() => [locked])
    await openEvents('/org/events?range=1h&severity=incident&user=3&target=4&q=192.0.2.44')

    const params = requests[0]
    expect(params.getAll('severity')).toEqual(['incident'])
    expect(params.get('user_id')).toBe('3')
    expect(params.get('target_user_id')).toBe('4')
    expect(params.get('ip_address')).toBe('192.0.2.44')
    expect(screen.getByRole('button', { name: 'Ultima oră', pressed: true })).toBeInTheDocument()
    expect(screen.getByText('Cont #3')).toBeInTheDocument()
    expect(screen.getByText('Țintă #4')).toBeInTheDocument()
    expect(screen.getByLabelText('Email sau adresă IP exactă')).toHaveValue('192.0.2.44')
  })

  it('searches an exact email or IP address, and clears the search', async () => {
    const user = userEvent.setup()
    const requests = serveEvents(() => [failed])
    const { router } = await openEvents()

    const input = screen.getByLabelText('Email sau adresă IP exactă')
    await user.type(input, 'mihai.pop@example.com{Enter}')
    expect(requests.at(-1)?.get('email')).toBe('mihai.pop@example.com')
    // Searching keeps the field, and the focus, in place.
    expect(input).toHaveFocus()
    expect(requests.at(-1)?.has('ip_address')).toBe(false)

    await user.clear(input)
    await user.type(input, '2001:db8::1{Enter}')
    expect(requests.at(-1)?.get('ip_address')).toBe('2001:db8::1')
    expect(requests.at(-1)?.has('email')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Șterge căutarea' }))
    expect(router.state.location.search).toBe('')
    expect(input).toHaveValue('')
  })

  it('removes a filter chip and resets every filter', async () => {
    const user = userEvent.setup()
    serveEvents(() => [locked])
    const { router } = await openEvents('/org/events?user=3&target=4&severity=warn')

    await user.click(screen.getByRole('button', { name: 'Elimină filtrul Cont #3' }))
    expect(router.state.location.search).toBe('?severity=warn&target=4')

    await user.click(screen.getByRole('button', { name: 'Resetează filtrele' }))
    expect(router.state.location.search).toBe('')
    expect(screen.queryByRole('button', { name: 'Resetează filtrele' })).not.toBeInTheDocument()
  })

  it('opens the details of an event and narrows the log from them', async () => {
    const user = userEvent.setup()
    const requests = serveEvents(() => [failed, locked])
    const { table, router } = await openEvents()

    await user.click(within(rows(table)[1]).getByRole('button', { name: 'Cont blocat temporar' }))

    const panel = await screen.findByRole('dialog', { name: 'Cont blocat temporar' })
    expect(panel).toHaveTextContent('Înregistrarea 502')
    expect(panel).toHaveTextContent('ioana.sec@example.com (utilizatorul #3)')
    expect(panel).toHaveTextContent('utilizatorul #4')
    expect(panel).toHaveTextContent('Reason: new country')
    expect(panel).toHaveTextContent('backend')

    await user.click(within(panel).getByRole('button', { name: 'Doar această țintă' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(router.state.location.search).toBe('?target=4')
    expect(requests.at(-1)?.get('target_user_id')).toBe('4')
  })

  it('marks detections with their MITRE ATT&CK technique and links it from the details', async () => {
    const user = userEvent.setup()
    const spray = makeSecurityEvent({
      id: 504,
      event_type: 'password_spray_detected',
      severity: 'incident',
      email: null,
      source: 'detection',
      message: 'Password spray from 203.0.113.9',
      mitre_technique: 'T1110.003',
      created_at: '2026-10-06T08:15:00Z',
      occurred_at: '2026-10-06T08:15:00Z',
    })
    serveEvents(() => [spray, failed])
    const { table } = await openEvents()

    const [first, second] = rows(table)
    expect(first).toHaveTextContent('Tehnica MITRE ATT&CK T1110.003')
    expect(within(first).getByTitle('Brute Force: Password Spraying')).toBeInTheDocument()
    expect(second).not.toHaveTextContent('MITRE')

    await user.click(within(first).getByRole('button', { name: 'Password spray detectat' }))
    const panel = await screen.findByRole('dialog', { name: 'Password spray detectat' })
    expect(panel).toHaveTextContent('T1110.003 · Brute Force: Password Spraying')
    const link = within(panel).getByRole('link', { name: /Deschide pe attack\.mitre\.org/ })
    expect(link).toHaveAttribute('href', 'https://attack.mitre.org/techniques/T1110/003/')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    // Raised as it happened: no separate time.
    expect(panel).not.toHaveTextContent('A avut loc')
  })

  it('shows when the event behind a late alert happened', async () => {
    const user = userEvent.setup()
    const late = makeSecurityEvent({
      id: 505,
      event_type: 'unfamiliar_sign_in',
      severity: 'warn',
      user_id: 4,
      source: 'detection',
      mitre_technique: 'T1078',
      created_at: '2026-10-06T09:00:00Z',
      occurred_at: '2026-10-06T06:30:00Z',
    })
    serveEvents(() => [late])
    const { table } = await openEvents()

    await user.click(
      within(rows(table)[0]).getByRole('button', { name: 'Autentificare din rețea și de pe dispozitiv nefamiliare' }),
    )

    const panel = await screen.findByRole('dialog')
    // The panel's heading time is when the alert was raised; this is the event's.
    const happened = within(panel).getByText('A avut loc').nextElementSibling
    expect(happened).toHaveTextContent(formatDateTime('2026-10-06T06:30:00Z', 'ro'))
    expect(happened).not.toHaveTextContent(formatDateTime('2026-10-06T09:00:00Z', 'ro'))
    expect(panel).toHaveTextContent(formatDateTime('2026-10-06T09:00:00Z', 'ro'))
    expect(panel).toHaveTextContent('T1078 · Valid Accounts')
  })

  it('opens the accounts an event names', async () => {
    const user = userEvent.setup()
    serveEvents(() => [failed, locked])
    const { table, router } = await openEvents()

    await user.click(within(rows(table)[1]).getByRole('button', { name: 'Cont blocat temporar' }))
    const panel = await screen.findByRole('dialog', { name: 'Cont blocat temporar' })
    expect(within(panel).getByRole('link', { name: 'Deschide contul' })).toHaveAttribute(
      'href',
      '/org/users/3',
    )

    await user.click(within(panel).getByRole('link', { name: 'Deschide ținta' }))

    expect(router.state.location.pathname).toBe('/org/users/4')
  })

  it('offers no account links for a failed sign-in that names no account', async () => {
    const user = userEvent.setup()
    serveEvents(() => [failed])
    const { table } = await openEvents()

    await user.click(within(rows(table)[0]).getByRole('button', { name: 'Autentificare eșuată' }))
    const panel = await screen.findByRole('dialog', { name: 'Autentificare eșuată' })

    expect(within(panel).queryByRole('link')).not.toBeInTheDocument()
  })

  it('filters a failed sign-in by the email it names, and opens rows by mouse', async () => {
    const user = userEvent.setup()
    const requests = serveEvents(() => [failed])
    const { table } = await openEvents()

    // A click anywhere on the row opens the details.
    await user.click(within(rows(table)[0]).getByText('203.0.113.9'))
    const panel = await screen.findByRole('dialog', { name: 'Autentificare eșuată' })
    await user.click(within(panel).getByRole('button', { name: 'Doar acest cont' }))

    expect(requests.at(-1)?.get('email')).toBe('mihai.pop@example.com')
    // The search field shows the filter set from the details.
    expect(screen.getByLabelText('Email sau adresă IP exactă')).toHaveValue('mihai.pop@example.com')
  })

  it('closes the details with Escape', async () => {
    const user = userEvent.setup()
    serveEvents(() => [failed])
    const { table } = await openEvents()

    await user.click(within(rows(table)[0]).getByRole('button', { name: 'Autentificare eșuată' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('loads older events with the cursor and the same time window', async () => {
    const user = userEvent.setup()
    const requests = serveEvents((params) =>
      params.get('before_id') === '502' ? [signedIn] : [[failed, locked], 502],
    )
    const { table } = await openEvents()

    await user.click(screen.getByRole('button', { name: 'Încarcă mai multe' }))

    await screen.findByText('Ai ajuns la începutul istoricului.')
    expect(rows(table)).toHaveLength(3)
    expect(requests[1].get('before_id')).toBe('502')
    expect(requests[1].get('since')).toBe(requests[0].get('since'))
  })

  it('refreshes from the first page', async () => {
    const user = userEvent.setup()
    const requests = serveEvents(() => [failed])
    await openEvents()

    await user.click(screen.getByRole('button', { name: 'Reîmprospătează' }))

    await screen.findByRole('table', { name: 'Evenimente de securitate' })
    expect(requests).toHaveLength(2)
    expect(requests[1].has('before_id')).toBe(false)
  })

  it('explains an invalid filter', async () => {
    serveEvents(() => HttpResponse.json({ detail: [] }, { status: 422 }))
    signedInAs(makeUser('admin'))
    renderApp('/org/events?q=999.1.1.1')

    expect(await screen.findByRole('alert')).toHaveTextContent('Filtrul nu este valid.')
  })

  it('tells an empty log apart from filters that match nothing', async () => {
    serveEvents(() => [])
    signedInAs(makeUser('admin'))
    const { unmount } = renderApp('/org/events')
    expect(await screen.findByText('Nu există înregistrări în intervalul ales.')).toBeInTheDocument()
    unmount()

    renderApp('/org/events?severity=incident')
    expect(await screen.findByText('Nicio înregistrare pentru filtrele alese.')).toBeInTheDocument()
  })
})
