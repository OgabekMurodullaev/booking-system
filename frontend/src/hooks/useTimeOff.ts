import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

export function useTimeOff(providerId: number | null) {
  return useQuery({
    queryKey: ['time-off', providerId],
    queryFn: () =>
      unwrap(
        apiClient.GET('/api/v1/providers/{provider_id}/time-off/', {
          params: { path: { provider_id: providerId as number } },
        }),
      ),
    enabled: providerId !== null,
  })
}
