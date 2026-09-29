/**
 * A fresh per-request key for the Idempotency-Key header. `crypto.randomUUID()` is only
 * available in a secure context (HTTPS, or localhost) — a plain-HTTP deployment (e.g. behind
 * a shared host's port workaround, with no TLS termination) has no `crypto.randomUUID` at all,
 * which threw synchronously and surfaced as a generic "Something went wrong" on every booking
 * attempt. This just needs to be unique per click, not cryptographically random, so a
 * Math.random()-based fallback is a correct, low-risk substitute rather than a new dependency.
 */
export function generateIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}
