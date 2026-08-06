import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import DownloadPage from "@/pages/public/download"

const { motionMock } = vi.hoisted(() => {
  const MockMotionDiv = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  return {
    motionMock: new Proxy({}, { get: () => MockMotionDiv }),
  }
})

vi.mock("motion/react", () => ({
  motion: motionMock,
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

describe("DownloadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, "alert").mockImplementation(() => {})
  })

  it("renders the primary download card", () => {
    render(<DownloadPage />)
    expect(screen.getAllByText(/Operion ERP/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Not Yet Available/i)).toBeInTheDocument()
  })

  it("renders the system requirements", () => {
    render(<DownloadPage />)
    expect(screen.getByText(/System Requirements/i)).toBeInTheDocument()
  })

  it("switches to the beta channel tab", async () => {
    const user = userEvent.setup()
    render(<DownloadPage />)
    await user.click(screen.getByRole("tab", { name: /beta/i }))
    expect(screen.getByRole("tab", { name: /beta/i })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("button", { name: /Request access/i })).toBeInTheDocument()
  })

  it("enters a beta email and requests access", async () => {
    const user = userEvent.setup()
    render(<DownloadPage />)
    await user.click(screen.getByRole("tab", { name: /beta/i }))
    const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement
    await user.type(input, "beta@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /Request access/i }))
    expect(window.alert).toHaveBeenCalled()
    expect(input.value).toBe("")
  })

  it("switches to the nightly channel tab", async () => {
    const user = userEvent.setup()
    render(<DownloadPage />)
    await user.click(screen.getByRole("tab", { name: /nightly/i }))
    expect(screen.getByRole("tab", { name: /nightly/i })).toHaveAttribute("aria-selected", "true")
    expect(screen.getAllByText(/Nightly Builds/i).length).toBeGreaterThan(0)
  })

  it("switches to the legacy versions tab", async () => {
    const user = userEvent.setup()
    render(<DownloadPage />)
    await user.click(screen.getByRole("tab", { name: /legacy/i }))
    expect(screen.getByText(/Previous Versions/i)).toBeInTheDocument()
  })

  it("triggers the docs bundle alert", () => {
    render(<DownloadPage />)
    fireEvent.click(screen.getByRole("button", { name: /Download docs bundle/i }))
    expect(window.alert).toHaveBeenCalled()
  })
})
