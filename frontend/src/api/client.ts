import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { ApiError } from './errors'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from './tokens'

const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
const RETRY_HEADER = 'X-Retried-After-Refresh'

export const apiClient = createClient<paths>({ baseUrl })

// Requests are cloned before they're sent (bodies are one-shot streams) so a 401 can
// replay the exact original request once a fresh access token is in hand.
const pendingRequests = new Map<string, Request>()

let refreshPromise: Promise<string> | null = null

async function performRefresh(): Promise<string> {
  const refresh = getRefreshToken()
  if (!refresh) {
    throw new ApiError('not_authenticated', 'No refresh token available.')
  }

  const response = await fetch(`${baseUrl}/api/v1/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })

  if (!response.ok) {
    clearTokens()
    throw new ApiError(
      'session_expired',
      'Your session has expired. Please log in again.',
    )
  }

  // Refresh rotation is on server-side: every call returns a NEW refresh token that
  // must replace the stored one, or the next refresh will fail.
  const data = (await response.json()) as { access: string; refresh: string }
  setAccessToken(data.access)
  setRefreshToken(data.refresh)
  return data.access
}

/** Single-flight: concurrent 401s all await the same in-flight refresh call. */
export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

apiClient.use({
  onRequest({ request, id }) {
    const token = getAccessToken()
    if (token) {
      request.headers.set('Authorization', `Bearer ${token}`)
    }
    pendingRequests.set(id, request.clone())
    return request
  },
  async onResponse({ request, response, id }) {
    const original = pendingRequests.get(id)
    pendingRequests.delete(id)

    if (response.status !== 401 || request.headers.has(RETRY_HEADER) || !original) {
      return response
    }

    try {
      const newToken = await refreshAccessToken()
      const retryRequest = original.clone()
      retryRequest.headers.set('Authorization', `Bearer ${newToken}`)
      retryRequest.headers.set(RETRY_HEADER, '1')
      return await fetch(retryRequest)
    } catch {
      return response
    }
  },
  onError({ id }) {
    pendingRequests.delete(id)
  },
})
