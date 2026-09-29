import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => unwrap(apiClient.GET('/api/v1/stats/')),
  })
}
