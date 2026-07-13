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
})

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

function getAccessToken(): string | null {
  return localStorage.getItem("operion-access-token")
}

// CSRF token management
function getCsrfToken(): string | null {
  // Read CSRF token from cookie (set by backend)
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  return match ? match[1] : null
}

function getRefreshToken(): string | null {
  return localStorage.getItem("operion-refresh-token")
}

function clearAuth() {
  localStorage.removeItem("operion-access-token")
  localStorage.removeItem("operion-refresh-token")
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

      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        clearAuth()
        isRefreshing = false
        processQueue(new Error("No refresh token"))
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login"
        }
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post<{ access_token: string; refresh_token: string }>(
          `${apiConfig.baseUrl}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        )
        localStorage.setItem("operion-access-token", data.access_token)
        localStorage.setItem("operion-refresh-token", data.refresh_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        processQueue(null, data.access_token)
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

    return Promise.reject(error)
  }
)

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
