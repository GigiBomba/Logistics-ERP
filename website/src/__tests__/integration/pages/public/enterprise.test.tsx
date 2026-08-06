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

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    enterpriseConfig: {
      contactEmail: "operion.contact@gmail.com",
      phoneNumber: "+40 123 456 789",
    },
  }
})

describe("EnterprisePage", () => {
  it("renders heading", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("Operion for Enterprise Fleets")).toBeInTheDocument()
  })

  it("renders enterprise features", () => {
    render(<EnterprisePage />)
    expect(screen.getByText("Enterprise Capabilities")).toBeInTheDocument()
    expect(screen.getByText(/Single Sign-On \(SSO\)/)).toBeInTheDocument()
    expect(screen.getByText(/SCIM user provisioning/)).toBeInTheDocument()
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
