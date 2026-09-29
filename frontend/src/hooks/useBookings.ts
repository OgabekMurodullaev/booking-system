import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { unwrap } from '@/api/errors'
import type { operations } from '@/api/schema'

type BookingsListQuery = NonNullable<
  operations['api_v1_bookings_list']['parameters']['query']
>

/** Unfiltered — My Bookings buckets Upcoming/Past/Cancelled from this single list client-side. */
export function useMyBookings() {
  return useQuery({
    queryKey: ['bookings'],
    queryFn: () => unwrap(apiClient.GET('/api/v1/bookings/')),
  })
}

/**
 * Shared by the provider schedule/approvals views and the admin all-bookings table — the
 * backend scopes results by role automatically (`_scoped_queryset`), so the same list
 * endpoint serves "my bookings as a provider" and "every booking in my business" alike.
 */
export function useBookingsList(query: BookingsListQuery) {
  return useQuery({
    queryKey: ['bookings', 'list', query],
    queryFn: () => unwrap(apiClient.GET('/api/v1/bookings/', { params: { query } })),
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
