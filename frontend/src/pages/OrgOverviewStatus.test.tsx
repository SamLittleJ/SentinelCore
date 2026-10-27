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

async function status() {
  signedInAs(makeUser('security_analyst'))
  renderApp('/org')
  return screen.findByRole('region', { name: 'Starea amenințărilor' })
}

describe('organization overview status', () => {
  it('shows the level and the latest detection, linking to its alerts', async () => {
    const latest = new Date(Date.now() - 50 * 60_000).toISOString()
    serveSummary({
      threat_level: 'incident',
      latest_detection: { technique: 'T1078', created_at: latest },
      techniques_7d: [
        { technique: 'T1078', alerts: 3, event_types: ['dormant_account_login', 'unfamiliar_sign_in'] },
      ],
    })

    const region = await status()

    expect(region).toHaveTextContent('Incident activ')
    // The link opens the alerts of that technique, in the audited event log.
    const link = within(region).getByRole('link', { name: 'T1078 Valid Accounts' })
    expect(link).toHaveAttribute('href', '/org/events?range=24h&type=dormant_account_login&type=unfamiliar_sign_in')
    expect(within(region).getByText(/\d/, { selector: 'time' })).toHaveAttribute('datetime', latest)
  })

  it('stays calm without detections', async () => {
    serveSummary({ threat_level: 'calm', latest_detection: null })

    const region = await status()

    expect(region).toHaveTextContent('Calm')
    expect(region).toHaveTextContent('Nicio detecție în ultimele 24 de ore')
    expect(within(region).queryByRole('link')).not.toBeInTheDocument()
  })

  it('writes the warning level in the warning color', async () => {
    serveSummary({ threat_level: 'warn' })

    const region = await status()

    expect(within(region).getByText('Atenție')).toHaveClass('text-sev-warn')
  })

  it('shows the status on the overview only', async () => {
    serveSummary({ threat_level: 'incident' })
    signedInAs(makeUser('admin'))
    renderApp('/org/audit')

    await screen.findByRole('heading', { level: 1, name: 'Jurnal de audit' })
    expect(screen.queryByRole('region', { name: 'Starea amenințărilor' })).not.toBeInTheDocument()
  })
})

describe('organization overview charts', () => {
  it('stacks the last 24 hours by severity, scaled to the busiest hour', async () => {
    serveSummary({ last_24h: { info: 4, warn: 3, incident: 1 }, hourly: busyHours() })
    signedInAs(makeUser('admin'))
    renderApp('/org')

    const section = await screen.findByRole('region', { name: 'Evenimente de securitate pe oră' })
    expect(
      within(section).getByText(/Ultimele 24 de ore — incidente: 1, avertismente: 3, evenimente informative: 4/),
    ).toHaveClass('sr-only')

    const hours = section.querySelectorAll<HTMLElement>('[title]')
    expect(hours).toHaveLength(24)
    expect(hours[22].getAttribute('title')).toMatch(/ — incidente: 1, avertismente: 2, informative: 0$/)
    // The busiest hours hold 4 events: hour 22 (1 incident, 2 warnings) and
    // hour 18 (4 informational).
    const [info, warn, incident] = hours[22].children as unknown as HTMLElement[]
    expect(incident).toHaveClass('bg-sev-incident')
    expect(incident.style.height).toBe('25%')
    expect(warn.style.height).toBe('50%')
    expect(info.style.height).toBe('0%')
    expect((hours[18].children[0] as HTMLElement).style.height).toBe('100%')
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
