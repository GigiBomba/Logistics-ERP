import { describe, it, expect, vi, beforeEach } from "vitest"
import { render } from "@/test-utils"
import { AppNavigate } from "@/components/navigation/app-navigate"

const navigateMock = vi.fn()

vi.mock("@/hooks/useAppNavigate", () => ({
  useAppNavigate: () => navigateMock,
}))

describe("AppNavigate", () => {
  beforeEach(() => vi.clearAllMocks())

  it("navigates to the given path on mount", () => {
    render(<AppNavigate to="/login" />)
    expect(navigateMock).toHaveBeenCalledWith("/login", { replace: false })
  })

  it("passes replace when requested", () => {
    render(<AppNavigate to="/dashboard" replace />)
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
  })

  it("re-navigates when the target path changes", () => {
    const { rerender } = render(<AppNavigate to="/a" />)
    rerender(<AppNavigate to="/b" />)
    expect(navigateMock).toHaveBeenCalledTimes(2)
    expect(navigateMock).toHaveBeenLastCalledWith("/b", { replace: false })
  })

  it("does not navigate again on unrelated re-renders", () => {
    const { rerender } = render(<AppNavigate to="/a" />)
    rerender(<AppNavigate to="/a" />)
    expect(navigateMock).toHaveBeenCalledTimes(1)
  })
})
