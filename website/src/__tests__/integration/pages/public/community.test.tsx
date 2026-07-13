import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import CommunityPage from "@/pages/public/community"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("CommunityPage", () => {
  it("renders heading", () => {
    render(<CommunityPage />)
    const headings = screen.getAllByText("Community")
    expect(headings.length).toBeGreaterThanOrEqual(1)
  })

  it("renders announcements", () => {
    render(<CommunityPage />)
    expect(screen.getByText("Operion ERP v1.0 Released")).toBeInTheDocument()
    expect(screen.getByText("Toolkit CLI Now Available")).toBeInTheDocument()
    expect(screen.getByText("Partnership with Geotab")).toBeInTheDocument()
  })

  it("renders community section cards", () => {
    render(<CommunityPage />)
    expect(screen.getByText("Community Guidelines")).toBeInTheDocument()
    expect(screen.getByText("Get Involved")).toBeInTheDocument()
    expect(screen.getByText("Showcase")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<CommunityPage />)
    expect(screen.getByText("Stay in the loop")).toBeInTheDocument()
  })
})
