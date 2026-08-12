import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, act } from "@/test-utils"
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

  it("renders all heading items", () => {
    render(<TableOfContents headings={mockHeadings} />)
    expect(screen.getByText("Section One")).toBeInTheDocument()
    expect(screen.getByText("Section Two")).toBeInTheDocument()
    expect(screen.getByText("Subsection One")).toBeInTheDocument()
  })

  it("applies different indentation for level 2 vs level 3 items", () => {
    render(<TableOfContents headings={mockHeadings} />)

    const links = screen.getAllByRole("link")
    // Level 2 items have pl-0, level 3 items have pl-4
    const sectionOneLink = links.find((l: HTMLElement) => l.textContent === "Section One")
    const subsectionLink = links.find((l: HTMLElement) => l.textContent === "Subsection One")

    expect(sectionOneLink?.className).toContain("pl-0")
    expect(subsectionLink?.className).toContain("pl-4")
  })

  it("scrolls to heading when clicked", () => {
    // Create a target element in the DOM so scrollIntoView is called
    const target = document.createElement("div")
    target.id = "section-1"
    document.body.appendChild(target)

    render(<TableOfContents headings={mockHeadings} />)

    const link = screen.getByText("Section One")
    fireEvent.click(link)

    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth" })

    document.body.removeChild(target)
  })

  it("renders links with correct href attributes", () => {
    render(<TableOfContents headings={mockHeadings} />)

    const link = screen.getByText("Section One").closest("a")
    expect(link).toHaveAttribute("href", "#section-1")
  })

  it("has sticky positioning class", () => {
    const { container } = render(<TableOfContents headings={mockHeadings} />)
    const nav = container.querySelector("nav")
    expect(nav?.className).toContain("sticky")
    expect(nav?.className).toContain("top-24")
  })

  it("returns null when there are no headings", () => {
    const { container } = render(<TableOfContents headings={[]} />)
    expect(container.innerHTML).toBe("")
  })

  it("extracts headings from the article element when none are provided", () => {
    const article = document.createElement("article")
    article.innerHTML =
      '<h2 id="alpha">Alpha</h2><h3>beta heading</h3><p>other</p>'
    document.body.appendChild(article)

    render(<TableOfContents />)
    const links = screen.getAllByRole("link").map((l) => l.textContent)
    expect(links).toEqual(["Alpha", "beta heading"])

    document.body.removeChild(article)
  })

  it("auto-generates an id for headings that lack one", () => {
    const article = document.createElement("article")
    article.innerHTML = "<h2>My Heading</h2>"
    document.body.appendChild(article)

    render(<TableOfContents />)
    const link = screen.getAllByRole("link").find((l) => l.textContent === "My Heading")
    expect(link).toHaveAttribute("href", "#my-heading")
    expect(article.querySelector("h2")?.id).toBe("my-heading")

    document.body.removeChild(article)
  })

  it("highlights the active heading based on the intersection observer", () => {
    let observerCallback: ((entries: IntersectionObserverEntry[]) => void) | undefined
    const OriginalIO = window.IntersectionObserver
    ;(window as any).IntersectionObserver = class {
      constructor(cb: (entries: IntersectionObserverEntry[]) => void) {
        observerCallback = cb
      }
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = vi.fn()
      root = null
      rootMargin = ""
      thresholds = []
      takeRecords = vi.fn()
    }

    const target = document.createElement("div")
    target.id = "section-2"
    document.body.appendChild(target)

    render(<TableOfContents headings={mockHeadings} />)
    expect(screen.getByText("Section Two").className).not.toContain("font-medium")

    act(() => {
      observerCallback?.([
        { isIntersecting: true, target } as unknown as IntersectionObserverEntry,
      ])
    })

    expect(screen.getByText("Section Two").className).toContain("font-medium")
    expect(screen.getByText("Section One").className).toContain("text-muted-foreground")

    document.body.removeChild(target)
    ;(window as any).IntersectionObserver = OriginalIO
  })
})
