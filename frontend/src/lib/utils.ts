import type { AxiosError } from 'axios';

/**
 * Extract a human-readable error message from an unknown caught value.
 *
 * FastAPI surfaces errors under `response.data.detail`. Falls back to the
 * JS Error message, then to `fallback` when nothing better is available.
 */
export function getApiError(err: unknown, fallback = 'An unexpected error occurred.'): string {
  const ax = err as AxiosError<{ detail?: string }>;
  if (ax?.response?.data?.detail) return ax.response.data.detail;
  if (err instanceof Error) return err.message;
  return fallback;
}
