import { useQuery } from '@tanstack/react-query'
import { get } from './client'
import type { SessionSummary, SessionDetail, Source } from '../types'

export function useSessions(project: string | null, source: Source) {
  return useQuery({
    queryKey: ['sessions', project, source],
    queryFn: () =>
      get<SessionSummary[]>('/api/sessions', {
        ...(project ? { project } : {}),
        ...(source ? { source } : {}),
        limit: '300',
      }),
    enabled: !!project,
    staleTime: 60_000,
  })
}

export function useSession(id: string | null) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => get<SessionDetail>(`/api/sessions/${id}`),
    enabled: !!id,
    staleTime: 5 * 60_000,
  })
}
