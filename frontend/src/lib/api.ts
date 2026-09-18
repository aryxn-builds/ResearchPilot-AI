/**
 * API client utilities for communicating with the ResearchPilot FastAPI backend.
 */

/**
 * Constructs a canonical API URL for requests to the FastAPI backend.
 *
 * Ensures:
 * 1. Base URL defaults to http://localhost:8000/api/v1 if not configured.
 * 2. Trailing slashes are stripped.
 * 3. The `/api/v1` prefix is automatically appended if omitted in NEXT_PUBLIC_API_URL.
 * 4. Double prefixes (e.g. `/api/v1/api/v1/...`) and duplicate slashes are eliminated.
 *
 * @param path - Endpoint path (e.g. '/research', 'research/123/report')
 * @returns Fully-qualified URL (e.g. 'https://api.example.com/api/v1/research')
 */
export function getApiUrl(path: string): string {
  const rawBase = process.env.NEXT_PUBLIC_API_URL?.trim() || 'http://localhost:8000/api/v1'

  // Clean trailing slashes from base URL
  let base = rawBase.replace(/\/+$/, '')

  // Ensure base URL includes the /api/v1 prefix expected by FastAPI
  if (!base.endsWith('/api/v1')) {
    base = `${base}/api/v1`
  }

  // Clean path: strip leading slashes
  let cleanPath = path.trim().replace(/^\/+/, '')

  // If path already starts with api/v1/, strip it to avoid double-prefixing
  if (cleanPath.startsWith('api/v1/')) {
    cleanPath = cleanPath.slice('api/v1/'.length)
  } else if (cleanPath === 'api/v1') {
    cleanPath = ''
  }

  return cleanPath ? `${base}/${cleanPath}` : base
}
