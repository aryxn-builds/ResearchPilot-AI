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
 * 4. Repeated `/api/v1` prefixes in the base or endpoint are collapsed.
 *
 * @param path - Endpoint path (e.g. '/research', 'research/123/report')
 * @returns Fully-qualified URL (e.g. 'https://api.example.com/api/v1/research')
 */
export function getApiUrl(path: string, baseUrl = process.env.NEXT_PUBLIC_API_URL): string {
  const rawBase = baseUrl?.trim() || 'http://localhost:8000'
  const base = rawBase.replace(/\/+$/, '').replace(/(?:\/api\/v1)+$/, '') + '/api/v1'
  const cleanPath = path.trim().replace(/^\/+/, '').replace(/^(?:api\/v1(?:\/|$))+/, '')

  return cleanPath ? `${base}/${cleanPath}` : base
}
