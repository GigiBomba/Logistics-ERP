import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ApiPlaygroundPage from "@/pages/public/api-playground"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ApiPlaygroundPage", () => {
  it("renders the page title", () => {
    render(<ApiPlaygroundPage />)
    expect(screen.getByText("API Playground")).toBeInTheDocument()
  })

  it("shows coming soon message", () => {
    render(<ApiPlaygroundPage />)
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
  })

  it("describes the upcoming interactive playground", () => {
    render(<ApiPlaygroundPage />)
    expect(
      screen.getByText(
        /we are actively developing our public api/i
      )
    ).toBeInTheDocument()
  })

  it("renders browse documentation link", () => {
    render(<ApiPlaygroundPage />)
    const docsLink = screen.getByText("Browse Documentation").closest("a")
    expect(docsLink).toHaveAttribute("href", "/docs")
  })

  it("renders the documentation button", () => {
    render(<ApiPlaygroundPage />)
    expect(
      screen.getByRole("link", { name: /browse documentation/i })
    ).toBeInTheDocument()
  })
})
