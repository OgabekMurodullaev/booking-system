import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

export function useServices() {
  return useQuery({
    queryKey: ['services'],
    queryFn: () => unwrap(apiClient.GET('/api/v1/services/')),
  })
}

export function useService(serviceId: number) {
  return useQuery({
    queryKey: ['services', serviceId],
    queryFn: () =>
      unwrap(
        apiClient.GET('/api/v1/services/{id}/', { params: { path: { id: serviceId } } }),
      ),
  })
}

export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: () => unwrap(apiClient.GET('/api/v1/providers/')),
    staleTime: 5 * 60 * 1000,
  })
}
