import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
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

vi.mock("@/config/site", () => ({
  pressConfig: {
    contactEmail: "operion.contact@gmail.com",
    companyFacts: {
      founded: "April 2026",
      headquarters: "Romania",
      employees: "1",
      customers: "0",
    },
  },
}))

describe("PressPage", () => {
  it("renders heading and tabs", () => {
    render(<PressPage />)
    expect(screen.getByText("Press & Media")).toBeInTheDocument()
    expect(screen.getByText("Press Releases")).toBeInTheDocument()
    expect(screen.getByText("Media Kit")).toBeInTheDocument()
  })

  it("renders press release cards", () => {
    render(<PressPage />)
    expect(
      screen.getByText("Operion Raises €12M Series A to Expand European Logistics Network")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Operion Launches AI-Powered Predictive Maintenance Module")
    ).toBeInTheDocument()
  })

  it("renders category badges on releases", () => {
    render(<PressPage />)
    expect(screen.getByText("Company")).toBeInTheDocument()
    expect(screen.getAllByText("Product").length).toBeGreaterThanOrEqual(1)
  })
})
