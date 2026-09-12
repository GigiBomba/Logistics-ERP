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

  it("shows the sandbox notice", () => {
    render(<ApiPlaygroundPage />)
    expect(screen.getByText("Sandbox — demo data only")).toBeInTheDocument()
    expect(
      screen.getByText(/This playground never makes live API requests/i)
    ).toBeInTheDocument()
  })

  it("renders the request builder controls", () => {
    render(<ApiPlaygroundPage />)
    expect(screen.getByText("Endpoint")).toBeInTheDocument()
    expect(screen.getByText("Method")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /send request/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument()
  })

  it("renders the response viewer placeholder", () => {
    render(<ApiPlaygroundPage />)
    expect(screen.getByText("Response")).toBeInTheDocument()
    expect(
      screen.getByText(/Send a request to see a simulated response here/i)
    ).toBeInTheDocument()
  })

  it("renders the rate limit note", () => {
    render(<ApiPlaygroundPage />)
    expect(
      screen.getByText(/Demo rate limit: 5 requests per 30 seconds/i)
    ).toBeInTheDocument()
  })
})
