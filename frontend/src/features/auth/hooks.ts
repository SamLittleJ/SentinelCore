import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/api'

import { fetchCurrentUser, logIn, logOut } from './api'

export const currentUserQueryKey = ['auth', 'currentUser'] as const

export function isUnauthenticated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: ({ signal }) => fetchCurrentUser(signal),
    // 401/403 are answers, not failures worth retrying.
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status < 500) && failureCount < 2,
    staleTime: 60_000,
  })
}

export function useLogIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      logIn(email, password),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: currentUserQueryKey }),
  })
}

export function useLogOut() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logOut,
    // Even if the request fails (for example an already expired session),
    // drop everything cached for the previous user.
    onSettled: () => queryClient.clear(),
  })
}
