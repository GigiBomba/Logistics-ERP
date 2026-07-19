import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import Error500Page from "@/pages/public/error-500"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("Error500Page", () => {
  it("renders 500 status code", () => {
    render(<Error500Page />)
    expect(screen.getByText("500")).toBeInTheDocument()
  })

  it("renders error heading", () => {
    render(<Error500Page />)
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
  })

  it("renders error description", () => {
    render(<Error500Page />)
    expect(
      screen.getByText(/something went wrong on our end/i)
    ).toBeInTheDocument()
  })

  it("renders try again button that triggers reload", () => {
    render(<Error500Page />)
    const tryAgainBtn = screen.getByText("Try Again")
    expect(tryAgainBtn).toBeInTheDocument()
  })

  it("renders go home link pointing to /", () => {
    render(<Error500Page />)
    const homeLink = screen.getByText("Go Home").closest("a")
    expect(homeLink).toHaveAttribute("href", "/")
  })

  it("renders contact support link pointing to /contact", () => {
    render(<Error500Page />)
    const contactLink = screen.getByText("Contact Support").closest("a")
    expect(contactLink).toHaveAttribute("href", "/contact")
  })

  it("renders all three action buttons", () => {
    render(<Error500Page />)
    // Try Again is a button, Go Home and Contact Support are links
    expect(screen.getByText("Try Again")).toBeInTheDocument()
    expect(screen.getByText("Go Home")).toBeInTheDocument()
    expect(screen.getByText("Contact Support")).toBeInTheDocument()
  })
})
