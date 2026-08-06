import axios, { AxiosError } from "axios"
import { apiConfig } from "@/config/site"
import type { ApiError } from "@/types"

declare module "axios" {
  interface InternalAxiosRequestConfig {
    _retry?: boolean
  }
}

const apiClient = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout, // React Query handles per-request cancellation via its `signal` prop automatically
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
})

let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error)
    } else {
      promise.resolve(token!)
    }
  })
  failedQueue = []
}

// CSRF token management
function getCsrfToken(): string | null {
  // Read CSRF token from cookie (set by backend)
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  return match ? match[1] : null
}

function clearAuth() {
  accessToken = null
  // Legacy cleanup — remove any tokens still in localStorage/sessionStorage
  localStorage.removeItem("operion-access-token")
  localStorage.removeItem("operion-refresh-token")
  sessionStorage.removeItem("operion-refresh-token")
}

/**
 * Exchange the httpOnly refresh cookie for a fresh access token.
 * The backend reads the refresh token from the httpOnly cookie, so the request
 * body must be empty (cookie is sent automatically via withCredentials).
 */
async function refreshAccessToken(): Promise<string | null> {
  try {
    const { data } = await axios.post<{ access_token: string }>(
      `${apiConfig.baseUrl}/api/v1/auth/refresh`,
      null,
      { withCredentials: true }
    )
    setAccessToken(data.access_token)
    return data.access_token
  } catch {
    return null
  }
}

apiClient.interceptors.request.use((config) => {
  // Add auth token
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Add CSRF token for state-changing methods
  const csrfToken = getCsrfToken()
  if (csrfToken && ["post", "put", "patch", "delete"].includes(config.method?.toLowerCase() || "")) {
    config.headers["X-CSRF-Token"] = csrfToken
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config

    if (!originalRequest || originalRequest._retry) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return apiClient(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      // Refresh via the httpOnly cookie (no body token needed).
      const freshToken = await refreshAccessToken()
      if (!freshToken) {
        clearAuth()
        isRefreshing = false
        processQueue(new Error("Session expired"))
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login"
        }
        return Promise.reject(error)
      }

      try {
        originalRequest.headers.Authorization = `Bearer ${freshToken}`
        processQueue(null, freshToken)
        return apiClient(originalRequest)
      } catch (refreshError) {
        clearAuth()
        processQueue(refreshError)
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login"
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    if (error.response?.status === 429) {
      const retryAfter = error.response.headers?.["retry-after"]
      console.warn(`[Rate Limited] Retry after: ${retryAfter || "unknown"}s`)
      // Intentionally NOT retrying — doing so would likely make the situation worse.
      // Individual callers (e.g. login page) may show their own toast with context-aware messages.
      return Promise.reject(error)
    }

    return Promise.reject(error)
  }
)

export function generateIdempotencyKey(): string {
  return `${Date.now()}-${crypto.randomUUID()}`
}

export function extractApiError(error: unknown): string {
  if (error instanceof AxiosError && error.response?.data) {
    const data = error.response.data as ApiError
    if (data.field_errors) {
      const messages = Object.values(data.field_errors).flat()
      return messages.join(". ")
    }
    return data.detail || error.message
  }
  if (error instanceof Error) return error.message
  return "An unexpected error occurred"
}

export default apiClient
