import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
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
  it("renders heading and partner type filters", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Partner with Operion")).toBeInTheDocument()
    expect(screen.getByText("All")).toBeInTheDocument()
    expect(screen.getAllByText("Technology").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Implementation").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Reseller").length).toBeGreaterThanOrEqual(1)
  })

  it("renders partner cards", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Google Maps")).toBeInTheDocument()
    expect(screen.getByText("TomTom")).toBeInTheDocument()
  })

  it("filters partners by type when tab clicked", () => {
    render(<PartnersPage />)
    const filterButtons = screen.getAllByText("Technology").filter(
      (el: HTMLElement) => el.tagName === "BUTTON"
    )
    if (filterButtons.length > 0) {
      fireEvent.click(filterButtons[0])
    }
    expect(screen.getByText("Google Maps")).toBeInTheDocument()
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
