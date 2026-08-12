import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText("Card content")).toBeInTheDocument()
  })

  it("applies base classes", () => {
    render(<Card>Card</Card>)
    const card = screen.getByText("Card")
    expect(card.className).toContain("rounded-xl")
    expect(card.className).toContain("border")
    expect(card.className).toContain("bg-card")
  })

  it("forwards className", () => {
    render(<Card className="custom-card">Card</Card>)
    expect(screen.getByText("Card").className).toContain("custom-card")
  })
})

describe("CardHeader", () => {
  it("renders children", () => {
    render(<CardHeader>Header</CardHeader>)
    expect(screen.getByText("Header")).toBeInTheDocument()
  })
})

describe("CardTitle", () => {
  it("renders as h3", () => {
    render(<CardTitle>Title</CardTitle>)
    const title = screen.getByText("Title")
    expect(title.tagName).toBe("H3")
    expect(title.className).toContain("font-semibold")
  })
})

describe("CardDescription", () => {
  it("renders description text", () => {
    render(<CardDescription>Description text</CardDescription>)
    const desc = screen.getByText("Description text")
    expect(desc.className).toContain("text-muted-foreground")
  })
})

describe("CardContent", () => {
  it("renders children", () => {
    render(<CardContent>Content</CardContent>)
    expect(screen.getByText("Content")).toBeInTheDocument()
  })
})

describe("CardFooter", () => {
  it("renders children", () => {
    render(<CardFooter>Footer</CardFooter>)
    expect(screen.getByText("Footer")).toBeInTheDocument()
  })
})

describe("Card composition", () => {
  it("composes Card with all sub-components", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Card Title</CardTitle>
          <CardDescription>Card description</CardDescription>
        </CardHeader>
        <CardContent>Main content</CardContent>
        <CardFooter>Footer actions</CardFooter>
      </Card>
    )
    expect(screen.getByText("Card Title")).toBeInTheDocument()
    expect(screen.getByText("Card description")).toBeInTheDocument()
    expect(screen.getByText("Main content")).toBeInTheDocument()
    expect(screen.getByText("Footer actions")).toBeInTheDocument()
  })
})
