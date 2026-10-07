import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { AuditLog } from '@/features/org/api'
import { renderApp } from '@/test/render'
import { makeAuditLog, makeUser, page, server, signedInAs } from '@/test/server'

const viewed = makeAuditLog()
const roleChanged = makeAuditLog({
  id: 899,
  event_type: 'user_role_changed',
  user_id: 1,
  target_user_id: 4,
  email: 'ana.owner@example.com',
  message: 'Owner changed role for user_id=4 from user to admin',
})
const loginFailed = makeAuditLog({
  id: 898,
  event_type: 'login_failed',
  user_id: null,
  email: 'nobody@example.com',
  message: null,
})

function serveAudit(respond: (params: URLSearchParams) => AuditLog[]) {
  const requests: URLSearchParams[] = []
  server.use(
    http.get('/api/admin/audit-logs', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(params)
      return HttpResponse.json(page(respond(params)))
    }),
  )
  return requests
}

async function openAudit(path = '/org/audit') {
  signedInAs(makeUser('admin'))
  const result = renderApp(path)
  const table = await screen.findByRole('table', { name: 'Jurnal de audit' })
  return { ...result, table, rows: within(table).getAllByRole('row').slice(1) }
}

describe('organization audit log page', () => {
  it('lists records and says that viewing them is recorded', async () => {
    serveAudit(() => [viewed, roleChanged, loginFailed])
    const { rows } = await openAudit()

    expect(screen.getByText(/Consultarea acestui jurnal este și ea înregistrată/)).toBeInTheDocument()
    expect(rows[0]).toHaveTextContent('Utilizatori consultați')
    expect(rows[0]).toHaveTextContent('ioana.sec@example.com')
    expect(rows[1]).toHaveTextContent('Rol schimbat')
    expect(rows[2]).toHaveTextContent('Autentificare eșuată')
    // The audit log has no severities.
    expect(screen.queryByRole('group', { name: 'Severitate' })).not.toBeInTheDocument()
  })

  it('filters by audit event type', async () => {
    const user = userEvent.setup()
    const requests = serveAudit(() => [roleChanged])
    const { router } = await openAudit()

    await user.click(screen.getByRole('button', { name: 'Tipuri de evenimente' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Cont blocat temporar' }))
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Rol schimbat' }))
    await user.keyboard('{Escape}')

    expect(requests.at(-1)?.getAll('event_type')).toEqual(['account_locked', 'user_role_changed'])
    expect(router.state.location.search).toBe('?type=account_locked&type=user_role_changed')

    await user.click(screen.getByRole('button', { name: 'Tipuri de evenimente' }))
    await user.click(screen.getByRole('menuitem', { name: 'Toate tipurile' }))
    expect(router.state.location.search).toBe('')
  })

  it('shows a record without a message and narrows to its target', async () => {
    const user = userEvent.setup()
    const requests = serveAudit(() => [roleChanged, loginFailed])
    const { rows } = await openAudit()

    await user.click(within(rows[1]).getByRole('button', { name: 'Autentificare eșuată' }))
    let panel = await screen.findByRole('dialog', { name: 'Autentificare eșuată' })
    expect(within(panel).getByText('Mesaj').nextSibling).toHaveTextContent('—')
    // No account and no target: only the email and the address narrow the log.
    expect(within(panel).queryByRole('button', { name: 'Doar această țintă' })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')

    await user.click(within(rows[0]).getByRole('button', { name: 'Rol schimbat' }))
    panel = await screen.findByRole('dialog', { name: 'Rol schimbat' })
    expect(panel).toHaveTextContent('Owner changed role for user_id=4 from user to admin')
    await user.click(within(panel).getByRole('button', { name: 'Doar această țintă' }))

    expect(requests.at(-1)?.get('target_user_id')).toBe('4')
  })
})
