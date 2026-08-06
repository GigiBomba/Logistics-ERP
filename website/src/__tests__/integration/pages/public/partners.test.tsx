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

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    partnerConfig: {
      contactEmail: "operion.contact@gmail.com",
    },
  }
})

describe("PartnersPage", () => {
  it("renders heading and partner benefits", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Partner with Operion")).toBeInTheDocument()
    expect(screen.getByText("Our Partners")).toBeInTheDocument()
    expect(screen.getAllByText(/Coming Soon/i).length).toBeGreaterThanOrEqual(1)
  })

  it("renders benefits section", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Become a Partner")).toBeInTheDocument()
    expect(screen.getByText("Revenue Share")).toBeInTheDocument()
    expect(screen.getByText("Co-Marketing")).toBeInTheDocument()
  })

  it("renders partner program section", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Partner Program")).toBeInTheDocument()
    expect(screen.getByText("Reseller Program Coming Soon")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<PartnersPage />)
    expect(screen.getByText("Apply to become a partner")).toBeInTheDocument()
  })
})
