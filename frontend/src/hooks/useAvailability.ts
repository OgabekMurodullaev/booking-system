import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

/**
 * Always fetched unfiltered (no `provider` param): a merged slot already lists every
 * provider free at that time in `provider_ids`, so a provider-specific view is just a
 * client-side filter over this one response — no second request needed.
 */
export function useAvailability(serviceId: number, dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: ['availability', serviceId, dateFrom, dateTo],
    queryFn: () =>
      unwrap(
        apiClient.GET('/api/v1/availability/', {
          params: { query: { service: serviceId, date_from: dateFrom, date_to: dateTo } },
        }),
      ),
  })
}
