import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

export function useWorkingHours(providerId: number | null) {
  return useQuery({
    queryKey: ['working-hours', providerId],
    queryFn: () =>
      unwrap(
        apiClient.GET('/api/v1/providers/{provider_id}/working-hours/', {
          params: { path: { provider_id: providerId as number } },
        }),
      ),
    enabled: providerId !== null,
  })
}
