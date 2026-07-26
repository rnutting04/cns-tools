import { QueryClient } from '@tanstack/react-query'

// Shared React Query client. Exported as a singleton so non-component code
// (e.g. AuthContext on logout) can imperatively clear all cached server state
// when the authenticated user changes — otherwise a newly logged-in user could
// briefly see the previous user's cached data.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data is considered fresh for 30s; within that window, navigating back to
      // a page serves the cache with no refetch (and no loading flash). After
      // that it refetches in the background.
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
