import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import DpaPage from "@/pages/public/dpa"

describe("DpaPage", () => {
  it("renders the page heading", () => {
    render(<DpaPage />)
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Data Processing Agreement (DPA)"
    )
  })

  it("renders the draft-template notice from the DPA document", () => {
    render(<DpaPage />)
    expect(screen.getByText(/DRAFT — for legal\/counsel review only/)).toBeInTheDocument()
  })

  it("renders the DPA document sections from public/dpa/operion-dpa.md", () => {
    render(<DpaPage />)
    expect(screen.getByRole("heading", { level: 2, name: /1\. Parties/ })).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { level: 3, name: /4\.1 Processor obligations/ })
    ).toBeInTheDocument()
    expect(screen.getByRole("cell", { name: "Controller (Customer)" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { level: 2, name: /Signature Block/ })).toBeInTheDocument()
  })
})