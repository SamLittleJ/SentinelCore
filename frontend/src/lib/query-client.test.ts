import { describe, expect, it } from 'vitest'

import { currentUserQueryKey } from '@/features/auth/hooks'
import { makeUser } from '@/test/server'

import { ApiError } from './api'
import { createQueryClient } from './query-client'

function clientWithSignedInUser() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  queryClient.setQueryData(currentUserQueryKey, makeUser())
  return queryClient
}

function currentUserState(queryClient: ReturnType<typeof createQueryClient>) {
  return queryClient.getQueryCache().find({ queryKey: currentUserQueryKey })!.state
}

describe('createQueryClient', () => {
  it('re-checks the current user when any request answers 401', async () => {
    const queryClient = clientWithSignedInUser()

    await queryClient
      .fetchQuery({
        queryKey: ['sessions'],
        queryFn: () => Promise.reject(new ApiError(401, 'Could not validate credentials', null)),
      })
      .catch(() => undefined)

    expect(currentUserState(queryClient).isInvalidated).toBe(true)
  })

  it.each([403, 404, 500])('leaves the current user alone on %i', async (status) => {
    const queryClient = clientWithSignedInUser()

    await queryClient
      .fetchQuery({
        queryKey: ['sessions'],
        queryFn: () => Promise.reject(new ApiError(status, 'error', null)),
      })
      .catch(() => undefined)

    expect(currentUserState(queryClient).isInvalidated).toBe(false)
  })
})
