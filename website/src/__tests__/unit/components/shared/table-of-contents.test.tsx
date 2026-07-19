import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { TableOfContents } from "@/components/shared/table-of-contents"

const mockHeadings = [
  { id: "section-1", text: "Section One", level: 2 as const },
  { id: "section-2", text: "Section Two", level: 2 as const },
  { id: "subsection-1", text: "Subsection One", level: 3 as const },
]

describe("TableOfContents", () => {
  it("renders 'On this page' heading", () => {
    render(<TableOfContents headings={mockHeadings} />)
    expect(screen.getByText("On this page")).toBeInTheDocument()
  })

  it("renders all heading items from props", () => {
    render(<TableOfContents headings={mockHeadings} />)
    expect(screen.getByText("Section One")).toBeInTheDocument()
    expect(screen.getByText("Section Two")).toBeInTheDocument()
    expect(screen.getByText("Subsection One")).toBeInTheDocument()
  })

  it("renders links with correct href attributes", () => {
    render(<TableOfContents headings={mockHeadings} />)
    const link = screen.getByText("Section One").closest("a")
    expect(link).toHaveAttribute("href", "#section-1")
  })

  it("renders nav element with sticky positioning class", () => {
    const { container } = render(<TableOfContents headings={mockHeadings} />)
    const nav = container.querySelector("nav")
    expect(nav?.className).toContain("sticky")
    expect(nav?.className).toContain("top-24")
  })

  it("returns null when headings array is empty", () => {
    const { container } = render(<TableOfContents headings={[]} />)
    expect(container.innerHTML).toBe("")
  })

  it("returns null when headings is undefined", () => {
    const { container } = render(<TableOfContents />)
    expect(container.innerHTML).toBe("")
  })

  it("renders level 2 headings without left padding", () => {
    render(<TableOfContents headings={mockHeadings} />)
    const links = screen.getAllByRole("link")
    const sectionOneLink = links.find((l) => l.textContent === "Section One")
    const sectionTwoLink = links.find((l) => l.textContent === "Section Two")
    expect(sectionOneLink?.className).toContain("pl-0")
    expect(sectionTwoLink?.className).toContain("pl-0")
  })

  it("renders level 3 headings with indentation (pl-4)", () => {
    render(<TableOfContents headings={mockHeadings} />)
    const links = screen.getAllByRole("link")
    const subsectionLink = links.find((l) => l.textContent === "Subsection One")
    expect(subsectionLink?.className).toContain("pl-4")
  })

  it("applies muted text color to non-active headings", () => {
    render(<TableOfContents headings={mockHeadings} />)
    const links = screen.getAllByRole("link")
    links.forEach((link) => {
      if (!link.className.includes("font-medium")) {
        expect(link.className).toContain("text-muted-foreground")
      }
    })
  })

  it("scrolls to heading section when link is clicked", () => {
    const target = document.createElement("div")
    target.id = "section-1"
    document.body.appendChild(target)

    render(<TableOfContents headings={mockHeadings} />)
    const link = screen.getByText("Section One")
    fireEvent.click(link)

    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    })

    document.body.removeChild(target)
  })

  it("calls scrollIntoView on the correct element by id", () => {
    const target = document.createElement("div")
    target.id = "subsection-1"
    document.body.appendChild(target)

    const scrollMock = vi.fn()
    Element.prototype.scrollIntoView = scrollMock

    render(<TableOfContents headings={mockHeadings} />)
    const link = screen.getByText("Subsection One")
    fireEvent.click(link)

    expect(scrollMock).toHaveBeenCalledWith({ behavior: "smooth" })

    document.body.removeChild(target)
  })

  it("prevents default anchor navigation on click", () => {
    const target = document.createElement("div")
    target.id = "section-1"
    document.body.appendChild(target)

    render(<TableOfContents headings={mockHeadings} />)
    const link = screen.getByText("Section One")
    const preventDefaultSpy = vi.spyOn(Event.prototype, "preventDefault")
    fireEvent.click(link)
    expect(preventDefaultSpy).toHaveBeenCalledTimes(1)

    document.body.removeChild(target)
    preventDefaultSpy.mockRestore()
  })

  function createIntersectionObserverMock() {
    let capturedCallback: IntersectionObserverCallback | null = null
    const MockObserver = vi.fn(function (this: any, callback: IntersectionObserverCallback) {
      capturedCallback = callback
      this.observe = vi.fn()
      this.unobserve = vi.fn()
      this.disconnect = vi.fn()
    }) as unknown as typeof IntersectionObserver

    // Helper to trigger an intersection for a given element
    const simulateIntersection = (elementId: string, isIntersecting: boolean) => {
      if (capturedCallback) {
        capturedCallback(
          [
            {
              target: document.getElementById(elementId)!,
              isIntersecting,
              intersectionRatio: isIntersecting ? 0.5 : 0,
              boundingClientRect: {} as DOMRect,
              intersectionRect: {} as DOMRect,
              rootBounds: null,
              time: 0,
            },
          ],
          null as unknown as IntersectionObserver
        )
      }
    }

    return { MockObserver, simulateIntersection }
  }

  it("applies font-medium class to active heading when corresponding element is intersecting", async () => {
    const { MockObserver, simulateIntersection } = createIntersectionObserverMock()

    const OriginalIntersectionObserver = window.IntersectionObserver
    window.IntersectionObserver = MockObserver

    const el1 = document.createElement("div")
    el1.id = "section-1"
    document.body.appendChild(el1)

    render(<TableOfContents headings={mockHeadings} />)

    simulateIntersection("section-1", true)

    await waitFor(() => {
      const link = screen.getByText("Section One")
      expect(link.className).toContain("font-medium")
      expect(link.className).toContain("text-foreground")
    })

    const sectionTwoLink = screen.getByText("Section Two")
    expect(sectionTwoLink.className).toContain("text-muted-foreground")

    document.body.removeChild(el1)
    window.IntersectionObserver = OriginalIntersectionObserver
  })

  it("switches active heading when a different element becomes intersecting", async () => {
    const { MockObserver, simulateIntersection } = createIntersectionObserverMock()

    const OriginalIntersectionObserver = window.IntersectionObserver
    window.IntersectionObserver = MockObserver

    const el1 = document.createElement("div")
    el1.id = "section-1"
    document.body.appendChild(el1)
    const el2 = document.createElement("div")
    el2.id = "section-2"
    document.body.appendChild(el2)

    render(<TableOfContents headings={mockHeadings} />)

    simulateIntersection("section-1", true)

    await waitFor(() => {
      expect(screen.getByText("Section One").className).toContain("font-medium")
    })

    simulateIntersection("section-2", true)

    await waitFor(() => {
      expect(screen.getByText("Section Two").className).toContain("font-medium")
      expect(screen.getByText("Section One").className).not.toContain("font-medium")
    })

    document.body.removeChild(el1)
    document.body.removeChild(el2)
    window.IntersectionObserver = OriginalIntersectionObserver
  })

  it("does not set active heading when no entries are intersecting", () => {
    const { MockObserver, simulateIntersection } = createIntersectionObserverMock()

    const OriginalIntersectionObserver = window.IntersectionObserver
    window.IntersectionObserver = MockObserver

    render(<TableOfContents headings={mockHeadings} />)

    simulateIntersection("section-1", false)

    const links = screen.getAllByRole("link")
    links.forEach((link) => {
      expect(link.className).toContain("text-muted-foreground")
    })

    window.IntersectionObserver = OriginalIntersectionObserver
  })

  it("renders list with space-y-1 class", () => {
    const { container } = render(<TableOfContents headings={mockHeadings} />)
    const ul = container.querySelector("ul")
    expect(ul?.className).toContain("space-y-1")
  })

  it("renders custom className on nav element", () => {
    const { container } = render(
      <TableOfContents headings={mockHeadings} className="custom-toc" />
    )
    const nav = container.querySelector("nav")
    expect(nav?.className).toContain("custom-toc")
  })

  it("has max height constraint class", () => {
    const { container } = render(<TableOfContents headings={mockHeadings} />)
    const nav = container.querySelector("nav")
    expect(nav?.className).toContain("max-h-[calc(100vh-8rem)]")
    expect(nav?.className).toContain("overflow-auto")
  })
})
