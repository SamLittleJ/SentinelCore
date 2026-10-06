import { QueryCache, QueryClient } from '@tanstack/react-query'

import { currentUserQueryKey, isUnauthenticated } from '@/features/auth/hooks'

const CURRENT_USER_HASH = JSON.stringify(currentUserQueryKey)

export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      // A 401 from any request means the session ended (expired, revoked or
      // logged out elsewhere). Re-checking the current user lets the route
      // guard send the user to the login page.
      onError: (error, query) => {
        if (isUnauthenticated(error) && query.queryHash !== CURRENT_USER_HASH) {
          void queryClient.invalidateQueries({ queryKey: currentUserQueryKey })
        }
      },
    }),
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: true,
      },
    },
  })
  return queryClient
}
