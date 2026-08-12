import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import RouteDemoPage from "@/pages/public/route-demo"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const mockPost = vi.fn()
vi.mock("@/api/client", () => ({
  default: {
    post: (...args: any[]) => mockPost(...args),
  },
}))

describe("RouteDemoPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders the hero section", () => {
    render(<RouteDemoPage />)
    expect(screen.getByText("Route Planner Demo")).toBeInTheDocument()
  })

  it("renders the form heading and description", () => {
    render(<RouteDemoPage />)
    expect(screen.getByText("Plan a Route")).toBeInTheDocument()
    expect(
      screen.getByText("Enter your origin and destination to get a live route comparison.")
    ).toBeInTheDocument()
  })

  it("renders origin and destination input fields", () => {
    render(<RouteDemoPage />)
    expect(screen.getByText("Origin city")).toBeInTheDocument()
    expect(screen.getByText("Destination city")).toBeInTheDocument()
  })

  it("renders the calculate button", () => {
    render(<RouteDemoPage />)
    expect(screen.getByRole("button", { name: /calculate route/i })).toBeInTheDocument()
  })

  it("calculate button is disabled when fields are empty", () => {
    render(<RouteDemoPage />)
    const button = screen.getByRole("button", { name: /calculate route/i })
    expect(button).toBeDisabled()
  })

  it("calculate button is enabled when both fields have text", () => {
    render(<RouteDemoPage />)
    const originInput = screen.getByPlaceholderText("e.g. Bucharest")
    const destInput = screen.getByPlaceholderText("e.g. Cluj-Napoca")

    fireEvent.change(originInput, { target: { value: "Berlin" } })
    fireEvent.change(destInput, { target: { value: "Munich" } })

    const button = screen.getByRole("button", { name: /calculate route/i })
    expect(button).toBeEnabled()
  })

  it("calls API with correct payload on calculate", async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        standard: {
          distance_km: 600,
          duration_hours: 7.5,
          fuelCost: 180,
          profit: 420,
          totalCost: 580,
        },
        optimized: {
          distance_km: 540,
          duration_hours: 6.8,
          fuelCost: 162,
          profit: 460,
          totalCost: 520,
        },
      },
    })

    render(<RouteDemoPage />)
    const originInput = screen.getByPlaceholderText("e.g. Bucharest")
    const destInput = screen.getByPlaceholderText("e.g. Cluj-Napoca")

    fireEvent.change(originInput, { target: { value: "Berlin" } })
    fireEvent.change(destInput, { target: { value: "Munich" } })

    fireEvent.click(screen.getByRole("button", { name: /calculate route/i }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/v1/route-demo/calculate", {
        origin: "Berlin",
        destination: "Munich",
      })
    })
  })

  it("renders CTA section at the bottom", () => {
    render(<RouteDemoPage />)
    expect(screen.getByText("Try Operion for free")).toBeInTheDocument()
    expect(screen.getByText("Get started")).toBeInTheDocument()
  })
})
