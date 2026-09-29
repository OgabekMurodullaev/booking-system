import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'

/** Unfiltered — My Bookings buckets Upcoming/Past/Cancelled from this single list client-side. */
export function useMyBookings() {
  return useQuery({
    queryKey: ['bookings'],
    queryFn: () => unwrap(apiClient.GET('/api/v1/bookings/')),
  })
}

export function useBookingDetail(bookingId: number | null) {
  return useQuery({
    queryKey: ['bookings', bookingId],
    queryFn: () =>
      unwrap(
        apiClient.GET('/api/v1/bookings/{id}/', {
          params: { path: { id: bookingId as number } },
        }),
      ),
    enabled: bookingId !== null,
  })
}
