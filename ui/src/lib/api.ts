const API_BASE = import.meta.env.VITE_API_BASE_URL || ""
// WARNING: VITE_ prefixed environment variables are bundled into client-side JavaScript
// and publicly readable. This is a transport-level identifier only, NOT a secret.
const API_KEY = import.meta.env.VITE_API_KEY || ""

function getAccessToken(): string | null {
  return localStorage.getItem("operion_access_token")
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY
  }
  const token = getAccessToken()
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }
  return headers
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers as Record<string, string> || {}),
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  postForm: <T>(path: string, body: Record<string, string>) => {
    const formData = new URLSearchParams(body)
    return request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData.toString(),
    })
  },
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserInfo {
  id: number
  email: string
  role: string
  company_id: number
  display_name: string
  company_name?: string
}

export function setTokens(tokens: AuthTokens, user?: UserInfo) {
  // Access token is short-lived (15 min); stored in localStorage for API calls.
  // Refresh token is set as an httpOnly cookie by the server — no longer
  // stored in localStorage (XSS protection).
  localStorage.setItem("operion_access_token", tokens.access_token)
  if (user) {
    localStorage.setItem("operion_user", JSON.stringify(user))
  }
}

export function clearTokens() {
  localStorage.removeItem("operion_access_token")
  localStorage.removeItem("operion_user")
}

export function getStoredUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("operion_user")
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function getStoredRefreshToken(): string | null {
  // Refresh token is now set as an httpOnly cookie by the server.
  // The browser sends it automatically with API requests to /api/v1/auth/.
  // This function returns null for the web frontend; the desktop client
  // still receives it in the JSON response body.
  return null
}
