import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ChangelogPage from "@/pages/public/changelog"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ChangelogPage", () => {
  it("renders Changelog heading", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("Changelog")).toBeInTheDocument()
  })

  it("shows coming soon message", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
    expect(
      screen.getByText(/building something great/i)
    ).toBeInTheDocument()
  })
})
