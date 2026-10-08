import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Role, User } from '@/features/auth/api'
import type { SecurityEvent } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeSecurityEvent, makeUser, page, server, signedInAs } from '@/test/server'

const HOUR = 60 * 60_000

const ACTORS: Record<Exclude<Role, 'user'>, User> = {
  owner: makeUser('owner', { id: 1, username: 'owner', email: 'owner@example.com' }),
  admin: makeUser('admin', { id: 2, username: 'ana.admin', email: 'ana.admin@example.com' }),
  security_analyst: makeUser('security_analyst', {
    id: 3,
    username: 'ioana.sec',
    email: 'ioana.sec@example.com',
  }),
}

const mihai = makeUser('user', {
  id: 12,
  username: 'mihai.pop',
  email: 'mihai.pop@example.com',
  created_at: '2026-09-01T10:00:00Z',
})

const roleChanged = makeSecurityEvent({
  id: 601,
  event_type: 'user_role_changed',
  severity: 'info',
  user_id: 1,
  target_user_id: 12,
  email: 'owner@example.com',
  ip_address: '192.0.2.1',
  message: 'Owner changed role for user_id=12 from user to security_analyst',
})
const signedIn = makeSecurityEvent({
  id: 600,
  event_type: 'login_success',
  severity: 'info',
  user_id: 12,
  email: 'mihai.pop@example.com',
  ip_address: '198.51.100.7',
})

interface Served {
  reads: number
  activityReads: number
  bodies: Record<string, unknown[]>
}

/** Serves `account` and its history, and records the actions taken on it.
 * Each action answers with `after`, the account as the action leaves it. */
function serveAccount(account: User, history: SecurityEvent[] = []): Served {
  const served: Served = { reads: 0, activityReads: 0, bodies: {} }
  let current = account
  const record = async (name: string, request: Request) => {
    const body: unknown = request.headers.get('Content-Type') ? await request.json() : null
    ;(served.bodies[name] ??= []).push(body)
  }
  const base = `/api/admin/users/${account.id}`
  server.use(
    http.get(base, () => {
      served.reads += 1
      return HttpResponse.json(current)
    }),
    http.get(`${base}/activity`, () => {
      served.activityReads += 1
      return HttpResponse.json(page(history))
    }),
    http.post(`${base}/revoke-sessions`, async ({ request }) => {
      await record('revoke', request)
      return HttpResponse.json({ revoked_sessions: 2 })
    }),
    http.post(`${base}/lock`, async ({ request }) => {
      await record('lock', request)
      current = { ...current, locked_until: new Date(Date.now() + 168 * HOUR).toISOString() }
      return HttpResponse.json(current)
    }),
    http.post(`${base}/unlock`, async ({ request }) => {
      await record('unlock', request)
      current = { ...current, locked_until: new Date(Date.now() - 1000).toISOString() }
      return HttpResponse.json(current)
    }),
    http.patch(`${base}/status`, async ({ request }) => {
      await record('status', request)
      const { is_active } = (served.bodies.status.at(-1) ?? {}) as { is_active: boolean }
      current = { ...current, is_active }
      return HttpResponse.json(current)
    }),
    http.patch(`${base}/role`, async ({ request }) => {
      await record('role', request)
      const { role } = (served.bodies.role.at(-1) ?? {}) as { role: Role }
      current = { ...current, role }
      return HttpResponse.json(current)
    }),
  )
  return served
}

async function openAccount(actor: User, account: User, history: SecurityEvent[] = []) {
  signedInAs(actor)
  const served = serveAccount(account, history)
  const result = renderApp(`/org/users/${account.id}`)
  await screen.findByRole('heading', { name: account.username, level: 1 })
  // The history has loaded too, so its loader is not mistaken for a notice.
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  return { ...result, served }
}

function actionButtons() {
  const section = screen.getByRole('region', { name: 'Acțiuni' })
  return within(section)
    .queryAllByRole('button')
    .map((button) => button.textContent)
}

describe('organization account page', () => {
  it("shows the account's profile and its history, described neutrally", async () => {
    const { served } = await openAccount(ACTORS.security_analyst, mihai, [roleChanged, signedIn])

    const title = screen.getByRole('heading', { name: 'mihai.pop', level: 1 }).parentElement
    expect(title).toHaveTextContent('mihai.pop@example.com')
    expect(title).toHaveTextContent('Activ')
    const table = await screen.findByRole('table', { name: 'Istoricul contului' })
    const [first, second] = within(table).getAllByRole('row').slice(1)
    expect(first).toHaveTextContent('Rol schimbat')
    expect(first).toHaveTextContent('owner@example.com')
    expect(second).toHaveTextContent('Autentificare reușită')
    expect(second).toHaveTextContent('198.51.100.7')
    expect(served.activityReads).toBe(1)
  })

  it('offers the analyst only the containment actions, even on a locked account', async () => {
    const locked = { ...mihai, locked_until: new Date(Date.now() + HOUR).toISOString() }
    await openAccount(ACTORS.security_analyst, locked)

    expect(screen.getByText(/^Blocat până la/)).toBeInTheDocument()
    expect(actionButtons()).toEqual(['Închide sesiunile', 'Blochează temporar'])
  })

  it('offers an admin unlocking and deactivation, but not role changes', async () => {
    const locked = { ...mihai, locked_until: new Date(Date.now() + HOUR).toISOString() }
    await openAccount(ACTORS.admin, locked)

    expect(actionButtons()).toEqual([
      'Închide sesiunile',
      'Blochează temporar',
      'Deblochează',
      'Dezactivează contul',
    ])
  })

  it("does not offer an admin another admin's status", async () => {
    const otherAdmin = makeUser('admin', { id: 13, username: 'dan.admin' })
    await openAccount(ACTORS.admin, otherAdmin)

    expect(actionButtons()).toEqual(['Închide sesiunile', 'Blochează temporar'])
  })

  it('offers the owner every action', async () => {
    const inactive = { ...mihai, is_active: false }
    await openAccount(ACTORS.owner, inactive)

    expect(screen.getByText('Dezactivat')).toBeInTheDocument()
    expect(actionButtons()).toEqual([
      'Închide sesiunile',
      'Blochează temporar',
      'Reactivează contul',
      'Schimbă rolul',
    ])
  })

  it("explains why one's own account and the owner's offer no actions", async () => {
    await openAccount(ACTORS.admin, ACTORS.admin)
    expect(screen.getByText(/Acesta este contul tău/)).toBeInTheDocument()
    expect(actionButtons()).toEqual([])
  })

  it("explains that the owner's account is protected", async () => {
    await openAccount(ACTORS.security_analyst, ACTORS.owner)
    expect(screen.getByText(/Contul proprietarului este protejat/)).toBeInTheDocument()
    expect(actionButtons()).toEqual([])
  })

  it('locks an account for the chosen time, with a reason', async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.security_analyst, mihai)

    await user.click(screen.getByRole('button', { name: 'Blochează temporar' }))
    const form = screen.getByRole('form', { name: 'Blochează temporar' })
    const confirm = within(form).getByRole('button', { name: 'Confirmă' })
    expect(within(form).getByRole('button', { name: '24 de ore', pressed: true })).toBeInTheDocument()

    // A reason shorter than the API accepts keeps the confirmation off.
    await user.type(within(form).getByLabelText('Motiv'), '  ab ')
    expect(confirm).toBeDisabled()

    await user.click(within(form).getByRole('button', { name: '7 zile' }))
    await user.type(within(form).getByLabelText('Motiv'), 'c new country')
    await user.click(confirm)

    expect(await screen.findByRole('status')).toHaveTextContent(/^Contul este blocat până la/)
    expect(served.bodies.lock).toEqual([{ duration_hours: 168, reason: 'ab c new country' }])
    // The account shows the lock without being read again; its history is.
    expect(screen.getByText(/^Blocat până la/)).toBeInTheDocument()
    expect(served.reads).toBe(1)
    await waitFor(() => expect(served.activityReads).toBe(2))
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
  })

  it("ends an account's sessions, with a reason", async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.security_analyst, mihai)

    await user.click(screen.getByRole('button', { name: 'Închide sesiunile' }))
    const form = screen.getByRole('form', { name: 'Închide sesiunile' })
    await user.type(within(form).getByLabelText('Motiv'), 'Sign-ins from an unknown country')
    await user.click(within(form).getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Am închis 2 sesiuni.')
    expect(served.bodies.revoke).toEqual([{ reason: 'Sign-ins from an unknown country' }])
  })

  it('cancels an action without sending it', async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.admin, mihai)

    await user.click(screen.getByRole('button', { name: 'Dezactivează contul' }))
    await user.click(screen.getByRole('button', { name: 'Anulează' }))

    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(served.bodies).toEqual({})
  })

  it('deactivates and reactivates an account', async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.admin, mihai)

    await user.click(screen.getByRole('button', { name: 'Dezactivează contul' }))
    const form = screen.getByRole('form', { name: 'Dezactivează contul' })
    // A confirmation without fields starts on its button.
    expect(within(form).getByRole('button', { name: 'Confirmă' })).toHaveFocus()
    await user.click(within(form).getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Contul a fost dezactivat.')
    expect(screen.getByText('Dezactivat')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reactivează contul' }))
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByText('Contul a fost reactivat.')).toBeInTheDocument()
    expect(served.bodies.status).toEqual([{ is_active: false }, { is_active: true }])
  })

  it('lifts a lock before it expires', async () => {
    const user = userEvent.setup()
    const locked = { ...mihai, locked_until: new Date(Date.now() + HOUR).toISOString() }
    const { served } = await openAccount(ACTORS.admin, locked)

    await user.click(screen.getByRole('button', { name: 'Deblochează' }))
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Blocarea a fost ridicată.')
    expect(served.bodies.unlock).toHaveLength(1)
    expect(screen.queryByText(/^Blocat până la/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Deblochează' })).not.toBeInTheDocument()
  })

  it("changes an account's role", async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.owner, mihai)

    await user.click(screen.getByRole('button', { name: 'Schimbă rolul' }))
    const form = screen.getByRole('form', { name: 'Schimbă rolul' })
    const confirm = within(form).getByRole('button', { name: 'Confirmă' })
    // The current role is chosen, and choosing it again changes nothing.
    expect(within(form).getByRole('button', { name: 'Utilizator', pressed: true })).toBeInTheDocument()
    expect(confirm).toBeDisabled()

    await user.click(within(form).getByRole('button', { name: 'Administrator' }))
    await user.click(confirm)

    expect(await screen.findByRole('status')).toHaveTextContent('Rolul este acum: Administrator.')
    expect(served.bodies.role).toEqual([{ role: 'admin' }])
  })

  it('explains a refused action and reads the account again', async () => {
    const user = userEvent.setup()
    const { served } = await openAccount(ACTORS.admin, mihai)
    server.use(
      http.patch('/api/admin/users/12/status', () =>
        HttpResponse.json({ detail: 'Only an owner can change the status of an admin' }, { status: 403 }),
      ),
    )

    await user.click(screen.getByRole('button', { name: 'Dezactivează contul' }))
    await user.click(screen.getByRole('button', { name: 'Confirmă' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Acțiunea nu este permisă pentru acest cont.')
    // The form stays open, so the operator sees what failed.
    expect(screen.getByRole('form', { name: 'Dezactivează contul' })).toBeInTheDocument()
    await waitFor(() => expect(served.reads).toBe(2))
  })

  it('says when the account does not exist', async () => {
    signedInAs(ACTORS.admin)
    server.use(
      http.get('/api/admin/users/99', () =>
        HttpResponse.json({ detail: 'User not found' }, { status: 404 }),
      ),
    )
    renderApp('/org/users/99')

    expect(await screen.findByText('Contul nu există')).toBeInTheDocument()
  })

  it('treats an address that is not an account id as not found', async () => {
    signedInAs(ACTORS.admin)
    renderApp('/org/users/abc')

    expect(await screen.findByText('Contul nu există')).toBeInTheDocument()
  })

  it('opens the other account an event names, not the one already shown', async () => {
    const user = userEvent.setup()
    const { router } = await openAccount(ACTORS.security_analyst, mihai, [roleChanged, signedIn])

    const table = await screen.findByRole('table', { name: 'Istoricul contului' })
    // The account's own sign-in names only this account.
    await user.click(within(table).getByRole('button', { name: 'Autentificare reușită' }))
    const own = await screen.findByRole('dialog', { name: 'Autentificare reușită' })
    expect(within(own).queryByRole('link')).not.toBeInTheDocument()
    await user.keyboard('{Escape}')

    await user.click(within(table).getByRole('button', { name: 'Rol schimbat' }))
    const panel = await screen.findByRole('dialog', { name: 'Rol schimbat' })

    expect(within(panel).queryByRole('link', { name: 'Deschide ținta' })).not.toBeInTheDocument()
    await user.click(within(panel).getByRole('link', { name: 'Deschide contul' }))
    expect(router.state.location.pathname).toBe('/org/users/1')
  })
})
