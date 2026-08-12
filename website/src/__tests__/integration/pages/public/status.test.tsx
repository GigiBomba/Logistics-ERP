import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import StatusPage from "@/pages/public/status"
import { useServiceStatus } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useServiceStatus: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  },
}))

const refetch = vi.fn()

const operationalData = [
  {
    name: "Components",
    services: [
      { name: "Desktop App", status: "operational", description: "Windows desktop client", updated_at: "2026-08-02T08:00:00Z" },
      { name: "Web Portal", status: "operational", description: "Web dashboard", updated_at: "2026-08-02T08:00:00Z" },
      { name: "API Backend", status: "operational", description: "REST API", updated_at: "2026-08-02T08:00:00Z" },
    ],
  },
]

describe("StatusPage with real data", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useServiceStatus).mockReturnValue({
      data: operationalData,
      isLoading: false,
      isError: false,
      refetch,
    } as any)
  })

  it("renders System Status heading", () => {
    render(<StatusPage />)
    expect(screen.getByText("System Status")).toBeInTheDocument()
  })

  it("shows an operational banner only when the data says so", () => {
    render(<StatusPage />)
    expect(screen.getAllByText("Operational").length).toBeGreaterThanOrEqual(1)
  })

  it("renders service names from the API", () => {
    render(<StatusPage />)
    expect(screen.getByText("Desktop App")).toBeInTheDocument()
    expect(screen.getByText("Web Portal")).toBeInTheDocument()
    expect(screen.getByText("API Backend")).toBeInTheDocument()
  })

  it("renders past incidents section", () => {
    render(<StatusPage />)
    expect(screen.getByText("Past Incidents")).toBeInTheDocument()
  })

  it("renders last updated timestamp", () => {
    render(<StatusPage />)
    expect(screen.getByText(/last updated/i)).toBeInTheDocument()
  })
})

describe("StatusPage without live data", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useServiceStatus).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as any)
  })

  it("shows an honest 'unavailable' banner and never a green pulse", () => {
    render(<StatusPage />)
    expect(screen.getByText("Status unavailable")).toBeInTheDocument()
    expect(screen.queryByText("Operational")).not.toBeInTheDocument()
    expect(screen.getAllByText("Status unknown").length).toBeGreaterThanOrEqual(1)
  })

  it("offers a retry button that re-fetches the status", () => {
    render(<StatusPage />)
    const retry = screen.getByRole("button", { name: "Try Again" })
    fireEvent.click(retry)
    expect(refetch).toHaveBeenCalled()
  })
})
