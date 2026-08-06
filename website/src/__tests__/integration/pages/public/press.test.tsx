import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import PressPage from "@/pages/public/press"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    pressConfig: {
      contactEmail: "operion.contact@gmail.com",
      companyFacts: {
        founded: "April 2026",
        headquarters: "Romania",
        employees: "1",
        customers: "0",
      },
    },
  }
})

describe("PressPage", () => {
  it("renders heading and tabs", () => {
    render(<PressPage />)
    expect(screen.getAllByText("Press & Media").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Press Releases")).toBeInTheDocument()
    expect(screen.getByText("Media Kit")).toBeInTheDocument()
  })

  it("renders media kit section with company facts", () => {
    render(<PressPage />)
    // Click on Media Kit tab to show its content
    const mediaKitTab = screen.getByText("Media Kit")
    fireEvent.click(mediaKitTab)
    expect(screen.getByText("Company Facts")).toBeInTheDocument()
    expect(screen.getByText("Press Contact")).toBeInTheDocument()
    expect(screen.getByText("operion.contact@gmail.com")).toBeInTheDocument()
  })

  it("renders company facts details", () => {
    render(<PressPage />)
    const mediaKitTab = screen.getByText("Media Kit")
    fireEvent.click(mediaKitTab)
    expect(screen.getByText("Founded")).toBeInTheDocument()
    expect(screen.getByText("Headquarters")).toBeInTheDocument()
  })
})
