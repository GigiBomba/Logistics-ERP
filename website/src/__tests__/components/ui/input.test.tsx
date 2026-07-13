import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Input, Label, Textarea } from "@/components/ui/input"

describe("Input", () => {
  it("renders with placeholder", () => {
    render(<Input placeholder="Enter name" />)
    expect(screen.getByPlaceholderText("Enter name")).toBeInTheDocument()
  })

  it("renders disabled state", () => {
    render(<Input disabled />)
    expect(screen.getByRole("textbox")).toBeDisabled()
  })

  it("applies custom className", () => {
    render(<Input className="custom" />)
    expect(screen.getByRole("textbox").className).toContain("custom")
  })

  it("forwards type attribute", () => {
    render(<Input type="email" />)
    expect(screen.getByRole("textbox")).toHaveAttribute("type", "email")
  })

  it("forwards value", () => {
    render(<Input value="test" readOnly />)
    expect(screen.getByRole("textbox")).toHaveValue("test")
  })
})

describe("Textarea", () => {
  it("renders with placeholder", () => {
    render(<Textarea placeholder="Enter description" />)
    expect(screen.getByPlaceholderText("Enter description")).toBeInTheDocument()
  })

  it("renders disabled state", () => {
    render(<Textarea disabled />)
    expect(screen.getByRole("textbox")).toBeDisabled()
  })

  it("forwards rows", () => {
    render(<Textarea rows={5} />)
    const textarea = screen.getByRole("textbox")
    expect(textarea).toHaveAttribute("rows", "5")
  })
})

describe("Label", () => {
  it("renders text content", () => {
    render(<Label>Email</Label>)
    expect(screen.getByText("Email")).toBeInTheDocument()
  })

  it("associates with input via htmlFor", () => {
    render(
      <>
        <Label htmlFor="email">Email</Label>
        <Input id="email" />
      </>
    )
    const label = screen.getByText("Email")
    expect(label).toHaveAttribute("for", "email")
  })

  it("applies custom className", () => {
    render(<Label className="custom-label">Name</Label>)
    expect(screen.getByText("Name").className).toContain("custom-label")
  })
})
