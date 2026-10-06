import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { TooltipProvider } from '@/components/ui/tooltip'
import { ThemeProvider } from '@/features/theme/ThemeProvider'
import { createQueryClient } from '@/lib/query-client'
import { appRoutes } from '@/routes'

/** Renders the real app routes at `path`, with fresh providers. */
export function renderApp(path: string) {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false, refetchOnWindowFocus: false } })
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })

  const result = render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <RouterProvider router={router} />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )

  return { ...result, router, queryClient }
}
