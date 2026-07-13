import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import CareersPage from "@/pages/public/careers"

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
  careersConfig: {
    contactEmail: "operion.contact@gmail.com",
  },
}))

describe("CareersPage", () => {
  it("renders heading", () => {
    render(<CareersPage />)
    expect(screen.getByText("Join Operion")).toBeInTheDocument()
  })

  it("renders culture values", () => {
    render(<CareersPage />)
    expect(screen.getByText("Innovation")).toBeInTheDocument()
    expect(screen.getByText("Collaboration")).toBeInTheDocument()
    expect(screen.getByText("Impact")).toBeInTheDocument()
    expect(screen.getByText("Growth")).toBeInTheDocument()
  })

  it("renders benefits", () => {
    render(<CareersPage />)
    expect(screen.getByText("Remote-first culture")).toBeInTheDocument()
    expect(screen.getByText("Flexible hours")).toBeInTheDocument()
    expect(screen.getByText("Learning budget")).toBeInTheDocument()
  })

  it("renders job openings", () => {
    render(<CareersPage />)
    expect(screen.getByText("Senior Frontend Engineer")).toBeInTheDocument()
    expect(screen.getByText("Backend Engineer (Rust)")).toBeInTheDocument()
    expect(screen.getByText("Product Designer")).toBeInTheDocument()
    expect(screen.getByText("DevOps Engineer")).toBeInTheDocument()
  })

  it("renders call-to-action banner", () => {
    render(<CareersPage />)
    expect(screen.getByText("Ready to build with us?")).toBeInTheDocument()
  })
})
