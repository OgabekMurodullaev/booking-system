import { refreshAccessToken } from '@/api/client'
import { ApiError } from '@/api/errors'
import { getAccessToken } from '@/api/tokens'

const baseUrl = import.meta.env.VITE_API_BASE_URL || ''

async function fetchIcs(
  bookingId: number,
  accessToken: string | null,
): Promise<Response> {
  return fetch(`${baseUrl}/api/v1/bookings/${bookingId}/calendar.ics`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  })
}

/** The .ics endpoint needs auth, so it can't be a plain `<a href>` — fetch as a blob instead. */
export async function downloadBookingIcs(bookingId: number): Promise<void> {
  let response = await fetchIcs(bookingId, getAccessToken())

  if (response.status === 401) {
    const newToken = await refreshAccessToken()
    response = await fetchIcs(bookingId, newToken)
  }

  if (!response.ok) {
    throw new ApiError('unknown_error', 'Could not download the calendar file.')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `booking-${bookingId}.ics`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
