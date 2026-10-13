type Tokens = { access_token: string; refresh_token: string }

export function apiUrl(path: string) {
  const baseUrl = import.meta.env.VITE_API_URL
  if (!baseUrl) throw new Error('ไม่พบที่อยู่เซิร์ฟเวอร์ API')
  return baseUrl.replace(/\/$/, '') + path
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function saveTokens(value: unknown): Tokens {
  const tokens = value as Partial<Tokens> | null
  if (!tokens || typeof tokens.access_token !== 'string' || !tokens.access_token
      || typeof tokens.refresh_token !== 'string' || !tokens.refresh_token) {
    throw new Error('ข้อมูลเข้าสู่ระบบไม่ถูกต้อง กรุณาลองใหม่')
  }
  localStorage.setItem('access_token', tokens.access_token)
  localStorage.setItem('refresh_token', tokens.refresh_token)
  return tokens as Tokens
}

export async function apiError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null)
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail)) {
    const messages = body.detail.map((item: { msg?: unknown }) => item?.msg)
      .filter((message: unknown): message is string => typeof message === 'string')
    if (messages.length) return messages.join(', ')
  }
  return fallback
}

let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  const response = await fetch(apiUrl('/refresh-token'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (response.status === 401 || response.status === 422) {
    clearTokens()
    return null
  }
  if (!response.ok) throw new Error('ต่ออายุการเข้าสู่ระบบไม่สำเร็จ กรุณาลองใหม่')
  return saveTokens(await response.json()).access_token
}

export async function authenticatedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const accessToken = localStorage.getItem('access_token')
  const headers = new Headers(options.headers)
  headers.set('Authorization', `Bearer ${accessToken ?? ''}`)
  const response = await fetch(apiUrl(path), { ...options, headers })
  if (response.status !== 401 || options.signal?.aborted) return response
  // One refresh per tab at a time prevents concurrent requests rotating the same token twice.
  if (!refreshInFlight) {
    refreshInFlight = refreshAccessToken().finally(() => { refreshInFlight = null })
  }
  const renewedToken = await refreshInFlight
  if (!renewedToken) return response
  headers.set('Authorization', `Bearer ${renewedToken}`)
  return fetch(apiUrl(path), { ...options, headers })
}
