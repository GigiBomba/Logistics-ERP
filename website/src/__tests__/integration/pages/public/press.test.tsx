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
      founded: "2026",
      headquarters: "Romania",
    },
  },
}))

describe("PressPage", () => {
  it("renders heading", () => {
    render(<PressPage />)
    const headings = screen.getAllByText("Press & Media")
    expect(headings.length).toBeGreaterThanOrEqual(1)
  })

  it("renders tabs", () => {
    render(<PressPage />)
    expect(screen.getByText("Press Releases")).toBeInTheDocument()
    expect(screen.getByText("Media Kit")).toBeInTheDocument()
  })
})
