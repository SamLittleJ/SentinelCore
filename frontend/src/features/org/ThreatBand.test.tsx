import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { SecuritySummary } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { emptyBuckets, makeSummary, makeUser, server, signedInAs } from '@/test/server'

const HOUR = 3600_000

function serveSummary(overrides: Partial<SecuritySummary>) {
  server.use(http.get('/api/security/summary', () => HttpResponse.json(makeSummary(overrides))))
}

/** The last 24 hours with, counted back from now, an incident 1 hour ago,
 * a warning 3 hours ago and an informational event 5 hours ago. */
function busyHours() {
  const hourly = emptyBuckets(24, HOUR)
  hourly[22].counts = { info: 0, warn: 2, incident: 1 }
  hourly[20].counts = { info: 0, warn: 1, incident: 0 }
  hourly[18].counts = { info: 4, warn: 0, incident: 0 }
  return hourly
}

async function band(path: string) {
  signedInAs(makeUser('security_analyst'))
  renderApp(path)
  return screen.findByRole('region', { name: 'Starea amenințărilor' })
}

describe('threat status band', () => {
  it('shows the level, the last 24 hours hour by hour and the latest detection', async () => {
    const latest = new Date(Date.now() - 50 * 60_000).toISOString()
    serveSummary({
      threat_level: 'incident',
      last_24h: { info: 4, warn: 3, incident: 1 },
      hourly: busyHours(),
      latest_detection: { technique: 'T1078', created_at: latest },
      techniques_7d: [
        { technique: 'T1078', alerts: 3, event_types: ['dormant_account_login', 'unfamiliar_sign_in'] },
      ],
    })

    const region = await band('/org/audit')

    expect(region).toHaveTextContent('Incident activ')
    expect(within(region).getByText(/Ultimele 24 de ore — incidente: 1, avertismente: 3, evenimente informative: 4/)).toHaveClass(
      'sr-only',
    )

    const cells = region.querySelectorAll('[title]')
    expect(cells).toHaveLength(24)
    expect(cells[22]).toHaveClass('bg-sev-incident')
    expect(cells[22].getAttribute('title')).toMatch(/ — incidente: 1, avertismente: 2, informative: 0$/)
    expect(cells[20]).toHaveClass('bg-sev-warn/75')
    expect(cells[18]).toHaveClass('bg-sev-info/45')
    expect(cells[0]).toHaveClass('bg-border')

    // The link opens the alerts of that technique, in the audited event log.
    const link = within(region).getByRole('link', { name: /^T1078 · / })
    expect(link).toHaveAttribute(
      'href',
      '/org/events?range=24h&type=dormant_account_login&type=unfamiliar_sign_in',
    )
    expect(within(link).getByText(/\d/, { selector: 'time' })).toHaveAttribute('datetime', latest)
  })

  it('stays calm without detections', async () => {
    serveSummary({ threat_level: 'calm', latest_detection: null })

    const region = await band('/org')

    expect(region).toHaveTextContent('Calm')
    expect(region).toHaveTextContent('Nicio detecție în ultimele 24 de ore')
    expect(within(region).queryByRole('link')).not.toBeInTheDocument()
  })

  it('warns with the warning color', async () => {
    serveSummary({ threat_level: 'warn' })

    const region = await band('/org/users')

    expect(region).toHaveTextContent('Atenție')
    expect(region).toHaveClass('border-t-sev-warn')
  })

  it('sits above organization pages only', async () => {
    let summaries = 0
    server.use(
      http.get('/api/security/summary', () => {
        summaries += 1
        return HttpResponse.json(makeSummary({ threat_level: 'incident' }))
      }),
    )
    signedInAs(makeUser('admin'))
    renderApp('/me')

    // The personal overview has loaded its own data; the band would have
    // asked for the counts at the same moment.
    await screen.findByRole('link', { name: 'Gestionează sesiunile' })
    expect(summaries).toBe(0)
    expect(screen.queryByRole('region', { name: 'Starea amenințărilor' })).not.toBeInTheDocument()
  })
})

describe('organization overview trends', () => {
  it('draws the last 7 days on each severity tile, scaled to the busiest day', async () => {
    const daily = emptyBuckets(7, 24 * HOUR)
    daily.forEach((day, index) => {
      day.counts = { info: 10, warn: index * 2, incident: index === 6 ? 4 : 0 }
    })
    serveSummary({ daily })
    signedInAs(makeUser('admin'))
    renderApp('/org')

    const tile = await screen.findByRole('link', { name: /^Incidente/ })
    const bars = tile.querySelectorAll<HTMLElement>('[aria-hidden] > span')
    expect(bars).toHaveLength(7)
    expect(bars[6].style.height).toBe('100%')
    expect(bars[6]).toHaveClass('bg-sev-incident')
    expect(bars[0]).toHaveClass('bg-border')

    const warnBars = screen
      .getByRole('link', { name: /^Avertismente/ })
      .querySelectorAll<HTMLElement>('[aria-hidden] > span')
    expect(warnBars[3].style.height).toBe('50%')
  })

  it('ranks the detected techniques and opens the alerts behind each', async () => {
    serveSummary({
      techniques_7d: [
        { technique: 'T1078', alerts: 12, event_types: ['dormant_account_login', 'unfamiliar_sign_in'] },
        { technique: 'T1110.003', alerts: 6, event_types: ['password_spray_detected'] },
      ],
    })
    signedInAs(makeUser('admin'))
    renderApp('/org')

    const list = await screen.findByRole('list', { name: 'Tehnici detectate' })
    const [first, second] = within(list).getAllByRole('link')
    expect(first).toHaveAccessibleName('T1078 Valid Accounts: 12 alerte')
    expect(first).toHaveAttribute('href', '/org/events?type=dormant_account_login&type=unfamiliar_sign_in')
    expect(second).toHaveAccessibleName('T1110.003 Brute Force: Password Spraying: 6 alerte')
    const bar = second.querySelector<HTMLElement>('[aria-hidden] > span')
    expect(bar?.style.width).toBe('50%')
  })

  it('says when no technique was detected', async () => {
    serveSummary({ techniques_7d: [] })
    signedInAs(makeUser('admin'))
    renderApp('/org')

    expect(await screen.findByText('Nicio alertă în ultimele 7 zile.')).toBeInTheDocument()
  })
})
