import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IntegrationsPage from "@/pages/public/integrations"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IntegrationsPage", () => {
  it("renders heading and category tabs", () => {
    render(<IntegrationsPage />)
    expect(screen.getAllByText("Integrations").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("All")).toBeInTheDocument()
    expect(screen.getAllByText("Telematics").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Accounting").length).toBeGreaterThanOrEqual(1)
  })

  it("renders integration cards", () => {
    render(<IntegrationsPage />)
    expect(screen.getByText("Google Maps")).toBeInTheDocument()
    expect(screen.getByText("TomTom")).toBeInTheDocument()
    expect(screen.getByText("HERE Maps")).toBeInTheDocument()
  })

  it("shows integration statuses", () => {
    render(<IntegrationsPage />)
    const statuses = screen.getAllByText("Available")
    expect(statuses.length).toBeGreaterThanOrEqual(1)
  })

  it("renders call-to-action section", () => {
    render(<IntegrationsPage />)
    expect(screen.getByText("Don't see your tool?")).toBeInTheDocument()
  })
})
