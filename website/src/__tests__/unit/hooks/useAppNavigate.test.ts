import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useAppNavigate } from "@/hooks/useAppNavigate"

const navigateMock = vi.fn()

vi.mock("vike/client/router", () => ({
  navigate: (...args: unknown[]) => navigateMock(...args),
}))

describe("useAppNavigate", () => {
  beforeEach(() => vi.clearAllMocks())

  it("returns a stable callback", () => {
    const { result, rerender } = renderHook(() => useAppNavigate())
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })

  it("navigates with overwriteLastHistoryEntry false by default", () => {
    const { result } = renderHook(() => useAppNavigate())
    act(() => result.current("/pricing"))
    expect(navigateMock).toHaveBeenCalledWith("/pricing", { overwriteLastHistoryEntry: false })
  })

  it("navigates with overwriteLastHistoryEntry true when replace is set", () => {
    const { result } = renderHook(() => useAppNavigate())
    act(() => result.current("/dashboard", { replace: true }))
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { overwriteLastHistoryEntry: true })
  })
})
