import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import MissionPage from "@/pages/public/mission"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("MissionPage", () => {
  it("renders page header", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Mission")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Building an AI operating system that executes logistics workflows — so transport companies can focus on decisions, not data entry."
      )
    ).toBeInTheDocument()
  })

  it("renders mission statement with quote", () => {
    render(<MissionPage />)
    // The blockquote wraps the quote with smart quotes as separate text nodes,
    // so we use a text match function that checks for inclusion.
    expect(
      screen.getByText((content) => content.includes("We're building the logistics platform we wish existed"))
    ).toBeInTheDocument()
  })

  it("renders Our Vision section", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Vision")).toBeInTheDocument()
  })

  it("renders What We Believe section with belief cards", () => {
    render(<MissionPage />)
    expect(screen.getByText("What We Believe")).toBeInTheDocument()
    expect(screen.getByText("Technology Should Do the Work")).toBeInTheDocument()
    expect(screen.getByText("Efficiency Drives Sustainability")).toBeInTheDocument()
  })

  it("renders Core Values section", () => {
    render(<MissionPage />)
    const valuesHeading = screen.getByText("Our Values")
    expect(valuesHeading).toBeInTheDocument()
  })

  it("renders Our Commitments section", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Commitments")).toBeInTheDocument()
  })

  it("renders stats section", () => {
    render(<MissionPage />)
    expect(screen.getByText("Open Development")).toBeInTheDocument()
    // The platforms label and value are identical ("Desktop + Mobile + Web")
    const platformsStats = screen.getAllByText("Desktop + Mobile + Web")
    expect(platformsStats.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Active Community")).toBeInTheDocument()
    expect(screen.getByText("Made in Romania")).toBeInTheDocument()
  })

  it("renders CTA section at the bottom", () => {
    render(<MissionPage />)
    expect(screen.getByText("Join us in building autonomous logistics")).toBeInTheDocument()
    expect(screen.getByText("Try Autonomous Dispatching")).toBeInTheDocument()
  })

  it("renders CTA link pointing to /register", () => {
    render(<MissionPage />)
    const registerLinks = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("href") === "/register")
    expect(registerLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("renders canonical link in helmet", () => {
    render(<MissionPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operionerp.xyz/mission")
  })
})
