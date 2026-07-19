import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import PartnersPage from "@/pages/public/partners"

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
  partnerConfig: {
    contactEmail: "operion.contact@gmail.com",
  },
}))

describe("PartnersPage", () => {
  it("renders heading", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Partner with Operion")).toBeInTheDocument()
  })

  it("renders partner benefits", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Revenue Share")).toBeInTheDocument()
    expect(screen.getByText("Early Access")).toBeInTheDocument()
  })

  it("renders partners heading section", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Our Partners")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<PartnersPage />)
    const ctaHeadings = screen.getAllByText("Become a Partner")
    expect(ctaHeadings.length).toBeGreaterThanOrEqual(1)
  })
})
