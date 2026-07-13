import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import EnterprisePage from "@/pages/public/enterprise"

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
  enterpriseConfig: {
    contactEmail: "operion.contact@gmail.com",
    phoneNumber: "+40 123 456 789",
  },
}))

describe("EnterprisePage", () => {
  it("renders heading", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("Operion Enterprise")).toBeInTheDocument()
  })

  it("renders enterprise overview cards", () => {
    render(<EnterprisePage />)
    expect(screen.getAllByText("Dedicated Infrastructure").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Custom Onboarding")).toBeInTheDocument()
    expect(screen.getByText("Priority Support")).toBeInTheDocument()
    expect(screen.getByText("SLA Guarantees")).toBeInTheDocument()
  })

  it("renders contact information", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("operion.contact@gmail.com")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("Get in Touch")).toBeInTheDocument()
  })
})
