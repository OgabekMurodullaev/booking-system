/**
 * Access token lives in memory only (module-level variable) — never persisted, so a
 * new tab or a full reload always starts from zero and must silently refresh. The
 * refresh token lives in localStorage since it needs to survive a reload.
 */
const REFRESH_TOKEN_STORAGE_KEY = 'booking_refresh_token'

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY)
}

export function setRefreshToken(token: string | null): void {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
  }
}

export function clearTokens(): void {
  setAccessToken(null)
  setRefreshToken(null)
}
