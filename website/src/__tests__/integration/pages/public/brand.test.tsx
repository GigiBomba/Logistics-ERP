import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import BrandPage from "@/pages/public/brand"

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
  pressConfig: {
    contactEmail: "operion.contact@gmail.com",
    companyFacts: {
      founded: "April 2026",
      headquarters: "Romania",
      employees: "1",
      customers: "0",
    },
  },
}))

describe("BrandPage", () => {
  it("renders heading", () => {
    render(<BrandPage />)
    expect(screen.getByText("Brand Guidelines")).toBeInTheDocument()
  })

  it("renders logo section", () => {
    render(<BrandPage />)
    expect(screen.getByText("Our Logo")).toBeInTheDocument()
  })

  it("renders logo variations", () => {
    render(<BrandPage />)
    expect(screen.getByText("Full Logo")).toBeInTheDocument()
    expect(screen.getByText("Icon Only")).toBeInTheDocument()
    expect(screen.getByText("Monochrome")).toBeInTheDocument()
  })

  it("renders color palette", () => {
    render(<BrandPage />)
    expect(screen.getByText("Color Palette")).toBeInTheDocument()
  })

  it("renders typography section", () => {
    render(<BrandPage />)
    expect(screen.getByText("Typography")).toBeInTheDocument()
  })
})
