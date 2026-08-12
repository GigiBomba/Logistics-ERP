import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import AboutPage from "@/pages/public/about"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("AboutPage", () => {
  it("renders the page title", () => {
    render(<AboutPage />)
    expect(screen.getByText("About Operion")).toBeInTheDocument()
  })

  it("renders the page subtitle", () => {
    render(<AboutPage />)
    expect(
      screen.getByText("Building logistics software that transport companies actually need.")
    ).toBeInTheDocument()
  })

  it("renders the company story section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Our Story")).toBeInTheDocument()
  })

  it("renders the story paragraphs", () => {
    render(<AboutPage />)
    expect(
      screen.getByText(
        /Operion started with a simple observation: transport companies were spending too much time/
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(/A team in Romania set out to build a better way/)
    ).toBeInTheDocument()
  })

  it("renders the mission section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Our Mission")).toBeInTheDocument()
  })

  it("renders mission CTA link to /mission", () => {
    render(<AboutPage />)
    const link = screen.getByRole("link", { name: /Join us/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/mission")
  })

  it("renders the values section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Our Values")).toBeInTheDocument()
  })

  it("renders all six core values", () => {
    render(<AboutPage />)
    expect(screen.getByText("Built for Real Needs")).toBeInTheDocument()
    expect(screen.getByText("Reliability First")).toBeInTheDocument()
    expect(screen.getByText("Practical Innovation")).toBeInTheDocument()
    expect(screen.getByText("Open Development")).toBeInTheDocument()
    expect(screen.getByText("Local-First")).toBeInTheDocument()
    expect(screen.getByText("Simple by Design")).toBeInTheDocument()
  })

  it("renders the technology stack section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Technology Stack")).toBeInTheDocument()
  })

  it("renders all four technology stack items", () => {
    render(<AboutPage />)
    expect(screen.getByText("Python & PySide6")).toBeInTheDocument()
    expect(screen.getByText("SQLite")).toBeInTheDocument()
    expect(screen.getByText("GraphHopper")).toBeInTheDocument()
    expect(screen.getByText("FastAPI Backend")).toBeInTheDocument()
  })

  it("renders the development philosophy section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Development Philosophy")).toBeInTheDocument()
  })

  it("renders all three philosophy items", () => {
    render(<AboutPage />)
    expect(screen.getByText("Quality Over Speed")).toBeInTheDocument()
    expect(screen.getByText("Iterative Development")).toBeInTheDocument()
    expect(screen.getByText("Clean Architecture")).toBeInTheDocument()
  })

  it("renders the company timeline section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Company Timeline")).toBeInTheDocument()
  })

  it("renders timeline items", () => {
    render(<AboutPage />)
    expect(screen.getByText("Project Started")).toBeInTheDocument()
    expect(screen.getByText("Route Planning Added")).toBeInTheDocument()
    expect(screen.getByText("Fleet Management & Documents")).toBeInTheDocument()
    expect(screen.getByText("Document Management")).toBeInTheDocument()
    expect(screen.getByText("Dispatch & Analytics")).toBeInTheDocument()
  })

  it("renders the team section", () => {
    render(<AboutPage />)
    expect(screen.getByText("Our Team")).toBeInTheDocument()
  })

  it("renders the team description text", () => {
    render(<AboutPage />)
    expect(
      screen.getByText(/Operion is built by a small, focused team based in Romania/)
    ).toBeInTheDocument()
  })

  it("renders the CTA section with register and contact links", () => {
    render(<AboutPage />)
    expect(
      screen.getByText(/Want to help shape the future of logistics software/)
    ).toBeInTheDocument()
    const downloadLink = screen.getByRole("link", { name: /Download Operion/i })
    expect(downloadLink).toHaveAttribute("href", "/register")
    const roadmapLink = screen.getByRole("link", { name: /View Roadmap/i })
    expect(roadmapLink).toHaveAttribute("href", "/contact")
  })

  it("renders canonical link", () => {
    render(<AboutPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/about")
  })
})
