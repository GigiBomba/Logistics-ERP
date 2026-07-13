import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import { QueryClientProvider, QueryClient } from "@tanstack/react-query"
import { type ReactNode } from "react"
import { authApi, subscriptionApi, companyApi, supportApi } from "@/api/endpoints"
import {
  useProfile,
  useUpdateProfile,
  useChangePassword,
  useSubscription,
  useCompany,
  useUpdateCompany,
  useCreateTicket,
  useTickets,
} from "@/services/queries"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthUser } from "@/test-utils"

vi.mock("@/api/endpoints", () => ({
  authApi: {
    getMe: vi.fn(),
    updateProfile: vi.fn(),
    changePassword: vi.fn(),
  },
  subscriptionApi: { getCurrent: vi.fn(), getPlans: vi.fn() },
  companyApi: { get: vi.fn(), update: vi.fn() },
  supportApi: { createTicket: vi.fn(), getTickets: vi.fn() },
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }

  return { wrapper: Wrapper, queryClient }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe("useProfile", () => {
  it("fetches profile when token exists", async () => {
    localStorage.setItem("operion-access-token", "token")
    vi.mocked(authApi.getMe).mockResolvedValueOnce({ data: { id: "1", name: "User" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useProfile(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(authApi.getMe).toHaveBeenCalled()
    expect(result.current.data).toEqual({ id: "1", name: "User" })
  })

  it("does not fetch when no token", () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useProfile(), { wrapper })
    expect(result.current.isFetching).toBe(false)
    expect(authApi.getMe).not.toHaveBeenCalled()
  })
})

describe("useUpdateProfile", () => {
  it("calls updateProfile on mutate", async () => {
    const updateUser = vi.fn()
    vi.mocked(useAuth).mockReturnValue({ updateUser } as any)
    vi.mocked(authApi.updateProfile).mockResolvedValueOnce({ data: { id: "1", name: "New" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateProfile(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ name: "New", email: "n@c.com" })
    })

    expect(authApi.updateProfile).toHaveBeenCalledWith({ name: "New", email: "n@c.com" })
    expect(updateUser).toHaveBeenCalled()
  })
})

describe("useChangePassword", () => {
  it("calls changePassword on mutate", async () => {
    vi.mocked(authApi.changePassword).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useChangePassword(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ current_password: "old", new_password: "new" })
    })

    expect(authApi.changePassword).toHaveBeenCalledWith({ current_password: "old", new_password: "new" })
  })
})

describe("useSubscription", () => {
  it("fetches subscription when token exists", async () => {
    localStorage.setItem("operion-access-token", "token")
    vi.mocked(subscriptionApi.getCurrent).mockResolvedValueOnce({ data: { plan_tier: "professional" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSubscription(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(subscriptionApi.getCurrent).toHaveBeenCalled()
    expect(result.current.data).toEqual({ plan_tier: "professional" })
  })

  it("does not fetch when no token", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useSubscription(), { wrapper })
    expect(subscriptionApi.getCurrent).not.toHaveBeenCalled()
  })
})

describe("useCompany", () => {
  it("fetches company when token exists", async () => {
    localStorage.setItem("operion-access-token", "token")
    vi.mocked(companyApi.get).mockResolvedValueOnce({ data: { name: "My Co" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCompany(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(companyApi.get).toHaveBeenCalled()
  })
})

describe("useUpdateCompany", () => {
  it("calls company update on mutate", async () => {
    vi.mocked(companyApi.update).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateCompany(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ name: "New Co" })
    })

    expect(companyApi.update).toHaveBeenCalledWith({ name: "New Co" })
  })
})

describe("useCreateTicket", () => {
  it("calls createTicket on mutate", async () => {
    vi.mocked(supportApi.createTicket).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateTicket(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ subject: "[Bug] Crash", description: "Details" })
    })

    expect(supportApi.createTicket).toHaveBeenCalledWith({ subject: "[Bug] Crash", description: "Details" })
  })
})

describe("useTickets", () => {
  it("fetches tickets when token exists", async () => {
    localStorage.setItem("operion-access-token", "token")
    vi.mocked(supportApi.getTickets).mockResolvedValueOnce({ data: [] } as any)

    const { wrapper } = createWrapper()
    renderHook(() => useTickets(), { wrapper })
    await waitFor(() => expect(supportApi.getTickets).toHaveBeenCalled())
  })
})
