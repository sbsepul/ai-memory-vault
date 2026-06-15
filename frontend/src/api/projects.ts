import { useQuery } from '@tanstack/react-query'
import { get } from './client'
import type { Project, Source } from '../types'

export function useProjects(source: Source) {
  return useQuery({
    queryKey: ['projects', source],
    queryFn: () => get<Project[]>('/api/projects', source ? { source } : undefined),
    staleTime: 60_000,
  })
}
