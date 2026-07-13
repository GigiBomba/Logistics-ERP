import { describe, it, expect, vi, beforeEach } from "vitest"
import apiClient, { extractApiError } from "@/api/client"
import { AxiosError } from "axios"

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
})

describe("apiClient interceptor", () => {
  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("localStorage", {
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

  it("attaches Authorization header when token exists", async () => {
    vi.mocked(localStorage.getItem).mockReturnValue("test-token")
    const config = await apiClient.interceptors.request.handlers[0].fulfilled({ headers: { set: vi.fn() } } as any)
    expect(config.headers.Authorization).toBe("Bearer test-token")
  })
})
