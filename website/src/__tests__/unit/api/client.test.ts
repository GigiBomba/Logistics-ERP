import { describe, it, expect, vi, beforeEach } from "vitest"
import apiClient, {
  extractApiError,
  setAccessToken,
  getAccessToken,
  generateIdempotencyKey,
} from "@/api/client"
import axios, { AxiosError } from "axios"

function makeAxiosError(
  status: number,
  config?: any,
  headers: Record<string, string> = {}
): AxiosError {
  const err = new AxiosError("Request failed", "ERR_BAD_REQUEST", config)
  err.response = {
    status,
    data: { detail: "error" },
    statusText: "Error",
    headers,
    config: config || { headers: {} },
  } as any
  return err
}

describe("extractApiError()", () => {
  it("extracts detail from ApiError response", () => {
    const error = new AxiosError("Request failed", "ERR_BAD_RESPONSE")
    error.response = { status: 400, data: { detail: "Invalid email" } } as any
    expect(extractApiError(error)).toBe("Invalid email")
  })

  it("extracts field errors", () => {
    const error = new AxiosError("", "ERR_BAD_RESPONSE")
    error.response = {
      status: 400,
      data: { detail: "Validation failed", field_errors: { email: ["Required"], password: ["Too short"] } },
    } as any
    const msg = extractApiError(error)
    expect(msg).toContain("Required")
    expect(msg).toContain("Too short")
  })

  it("returns message for generic Error", () => {
    expect(extractApiError(new Error("Network error"))).toBe("Network error")
  })

  it("returns fallback for unknown error", () => {
    expect(extractApiError(null)).toBe("An unexpected error occurred")
  })

  it("returns fallback for string error", () => {
    expect(extractApiError("raw string")).toBe("An unexpected error occurred")
  })

  it("prefers detail over message when both present", () => {
    const error = new AxiosError("Request failed", "ERR_BAD_RESPONSE")
    error.response = { status: 500, data: { detail: "Server exploded" } } as any
    expect(extractApiError(error)).toBe("Server exploded")
  })
})

describe("apiClient request interceptor", () => {
  const requestHandler = apiClient.interceptors.request.handlers![0]!

  beforeEach(() => {
    vi.clearAllMocks()
    setAccessToken(null)
    // Clear the CSRF cookie between tests
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/"
  })

  it("attaches Authorization header when token exists", async () => {
    setAccessToken("test-token")
    const config = await requestHandler.fulfilled({ headers: {} } as any)
    expect(config.headers.Authorization).toBe("Bearer test-token")
  })

  it("does not attach Authorization when no token", async () => {
    const config = await requestHandler.fulfilled({ headers: {} } as any)
    expect(config.headers.Authorization).toBeUndefined()
  })

  it("attaches CSRF token for state-changing methods", async () => {
    document.cookie = "csrf_token=abc-123"
    const config = await requestHandler.fulfilled({ headers: {}, method: "post" } as any)
    expect(config.headers["X-CSRF-Token"]).toBe("abc-123")
  })

  it("does not attach CSRF token for GET", async () => {
    document.cookie = "csrf_token=abc-123"
    const config = await requestHandler.fulfilled({ headers: {}, method: "get" } as any)
    expect(config.headers["X-CSRF-Token"]).toBeUndefined()
  })

  it("does not attach CSRF token when cookie is missing", async () => {
    const config = await requestHandler.fulfilled({ headers: {}, method: "delete" } as any)
    expect(config.headers["X-CSRF-Token"]).toBeUndefined()
  })
})

describe("apiClient response interceptor", () => {
  const responseHandler = apiClient.interceptors.response.handlers![0]!
  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    setAccessToken(null)
    vi.restoreAllMocks()
    vi.stubGlobal("sessionStorage", {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(),
    })
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, href: "" },
      writable: true,
    })
  })

  it("passes successful responses through", async () => {
    const res = {
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
      config: { headers: {} },
    }
    expect(responseHandler.fulfilled!(res as any)).toBe(res)
  })

  it("rejects when there is no original request", async () => {
    const err = makeAxiosError(401, undefined)
    await expect(responseHandler.rejected!(err)).rejects.toBe(err)
  })

  it("rejects immediately when the request was already retried", async () => {
    const err = makeAxiosError(401, { _retry: true })
    await expect(responseHandler.rejected!(err)).rejects.toBe(err)
  })

  it("refreshes the token and retries the request on 401", async () => {
    const postSpy = vi.spyOn(axios, "post").mockResolvedValueOnce({
      data: { access_token: "fresh-token" },
    })
    setAccessToken("old-token")

    const config = { headers: {}, url: "/api/v1/me", method: "get" }
    const adapter = vi
      .fn()
      .mockRejectedValueOnce(makeAxiosError(401, config))
      .mockResolvedValueOnce({
        data: { ok: true },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      })
    ;(apiClient as any).defaults.adapter = adapter

    const res = await apiClient.get("/api/v1/me")
    expect(res.data).toEqual({ ok: true })
    expect(postSpy).toHaveBeenCalledWith("/api/v1/auth/refresh", null, { withCredentials: true })
    expect(getAccessToken()).toBe("fresh-token")
    // Retry request carried the fresh bearer token
    const retryConfig = adapter.mock.calls[1][0]
    expect(retryConfig.headers.Authorization).toBe("Bearer fresh-token")
  })

  it("clears auth and redirects to /login when refresh fails", async () => {
    vi.spyOn(axios, "post").mockRejectedValueOnce(new Error("network down"))
    setAccessToken("expired-token")

    const config = { headers: {}, url: "/api/v1/me", method: "get" }
    const adapter = vi.fn().mockRejectedValueOnce(makeAxiosError(401, config))
    ;(apiClient as any).defaults.adapter = adapter

    await expect(apiClient.get("/api/v1/me")).rejects.toThrow()
    expect(getAccessToken()).toBeNull()
    expect(window.location.href).toBe("/login")
    expect(localStorage.removeItem).toHaveBeenCalledWith("operion-access-token")
    expect(sessionStorage.removeItem).toHaveBeenCalledWith("operion-refresh-token")
  })

  it("does not redirect when already on the login page", async () => {
    vi.spyOn(axios, "post").mockRejectedValueOnce(new Error("network down"))
    setAccessToken("expired-token")
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, href: "", pathname: "/login" },
      writable: true,
    })

    const config = { headers: {}, url: "/api/v1/me", method: "get" }
    const adapter = vi.fn().mockRejectedValueOnce(makeAxiosError(401, config))
    ;(apiClient as any).defaults.adapter = adapter

    await expect(apiClient.get("/api/v1/me")).rejects.toThrow()
    expect(window.location.href).toBe("")
  })

  it("queues concurrent 401 requests and retries them after refresh", async () => {
    let resolveRefresh!: (v: unknown) => void
    const refreshPromise = new Promise((r) => {
      resolveRefresh = r
    })
    vi.spyOn(axios, "post")
      .mockReturnValueOnce(refreshPromise as any)
      .mockResolvedValueOnce({ data: { access_token: "fresh-token" } })
    setAccessToken("old-token")

    const errA = makeAxiosError(401, { headers: {}, url: "/a", method: "get" })
    const errB = makeAxiosError(401, { headers: {}, url: "/b", method: "get" })
    const adapter = vi
      .fn()
      .mockRejectedValueOnce(errA)
      .mockRejectedValueOnce(errB)
      .mockResolvedValueOnce({
        data: { ok: "a" },
        status: 200,
        statusText: "OK",
        headers: {},
        config: {},
      })
      .mockResolvedValueOnce({
        data: { ok: "b" },
        status: 200,
        statusText: "OK",
        headers: {},
        config: {},
      })
    ;(apiClient as any).defaults.adapter = adapter

    const p1 = apiClient.get("/a")
    const p2 = apiClient.get("/b")

    // Let both rejections reach the interceptor before resolving the refresh
    await new Promise((r) => setTimeout(r, 10))
    expect(axios.post).toHaveBeenCalledTimes(1)

    resolveRefresh({ data: { access_token: "fresh-token" } })
    const [r1, r2] = await Promise.all([p1, p2])
    expect(r1.data).toEqual({ ok: "a" })
    expect(r2.data).toEqual({ ok: "b" })
    expect(adapter).toHaveBeenCalledTimes(4)
  })

  it("rejects queued requests when refresh fails", async () => {
    let resolveRefresh!: (v: unknown) => void
    const refreshPromise = new Promise((r) => {
      resolveRefresh = r
    })
    vi.spyOn(axios, "post").mockReturnValueOnce(refreshPromise as any)
    setAccessToken("old-token")

    const errA = makeAxiosError(401, { headers: {}, url: "/a", method: "get" })
    const errB = makeAxiosError(401, { headers: {}, url: "/b", method: "get" })
    const adapter = vi.fn().mockRejectedValueOnce(errA).mockRejectedValueOnce(errB)
    ;(apiClient as any).defaults.adapter = adapter

    const p1 = apiClient.get("/a")
    const p2 = apiClient.get("/b")
    await new Promise((r) => setTimeout(r, 10))

    resolveRefresh(new Error("network down"))
    await expect(p1).rejects.toBeDefined()
    await expect(p2).rejects.toBeDefined()
    expect(getAccessToken()).toBeNull()
  })

  it("warns and rejects on 429 with retry-after header", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    const err = makeAxiosError(429, { headers: {}, url: "/x", method: "get" }, { "retry-after": "5" })
    await expect(responseHandler.rejected!(err)).rejects.toBe(err)
    expect(warn).toHaveBeenCalledWith("[Rate Limited] Retry after: 5s")
  })

  it("warns with unknown retry-after on 429", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    const err = makeAxiosError(429, { headers: {}, url: "/x", method: "get" })
    await expect(responseHandler.rejected!(err)).rejects.toBe(err)
    expect(warn).toHaveBeenCalledWith("[Rate Limited] Retry after: unknowns")
  })

  it("rejects on non-401/429 errors without side effects", async () => {
    const err = makeAxiosError(500, { headers: {}, url: "/x", method: "get" })
    await expect(responseHandler.rejected!(err)).rejects.toBe(err)
    expect(getAccessToken()).toBeNull()
    expect(window.location.href).toBe("")
  })
})

describe("generateIdempotencyKey", () => {
  it("returns a timestamp-prefixed UUID", () => {
    const key = generateIdempotencyKey()
    expect(key).toMatch(/^\d{13}-[0-9a-f-]{36}$/)
  })

  it("returns unique keys", () => {
    expect(generateIdempotencyKey()).not.toBe(generateIdempotencyKey())
  })
})

