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

  it("renders planned capabilities", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("Planned Enterprise Capabilities")).toBeInTheDocument()
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
