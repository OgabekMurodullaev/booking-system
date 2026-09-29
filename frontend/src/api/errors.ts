/** Typed mirror of the backend's `{"error": {"code","message","details"}}` envelope (CLAUDE.md §7). */
export class ApiError extends Error {
  readonly code: string
  readonly details?: Record<string, unknown>

  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
  }
}

interface ErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === 'object' && value !== null && 'error' in value
}

/**
 * Unwraps an openapi-fetch result into its typed `data`, or throws a normalized
 * ApiError built from the backend's error envelope (or a generic fallback for
 * anything that isn't that shape — a network failure, a raw 500, etc).
 */
export async function unwrap<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error } = await result
  if (data !== undefined) return data

  if (isErrorEnvelope(error) && error.error) {
    throw new ApiError(
      error.error.code ?? 'unknown_error',
      error.error.message ?? 'Something went wrong.',
      error.error.details,
    )
  }

  throw new ApiError('unknown_error', 'Something went wrong. Please try again.')
}
