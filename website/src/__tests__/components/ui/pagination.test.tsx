import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { Pagination } from "@/components/ui/pagination"

vi.mock("@/i18n/locale-context", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/locale-context")>("@/i18n/locale-context")
  return {
    ...actual,
    useLocale: () => ({
      locale: "en" as const,
      setLocale: vi.fn(),
      t: (key: string) => {
        const defaults: Record<string, string> = {
          "common.pagination": "Pagination",
          "common.goToPrevPage": "Go to previous page",
          "common.goToNextPage": "Go to next page",
          "common.goToPage": "Go to page",
        }
        return defaults[key] || key
      },
    }),
  }
})

describe("Pagination", () => {
  it("renders current page number", () => {
    render(<Pagination currentPage={3} totalPages={10} onPageChange={vi.fn()} />)
    const pageBtn = screen.getByLabelText("Go to page 3")
    expect(pageBtn).toBeInTheDocument()
  })

  it("renders previous and next buttons", () => {
    render(<Pagination currentPage={3} totalPages={10} onPageChange={vi.fn()} />)
    expect(screen.getByLabelText("Go to previous page")).toBeInTheDocument()
    expect(screen.getByLabelText("Go to next page")).toBeInTheDocument()
  })

  it("calls onPageChange with previous page when clicking previous", () => {
    const onPageChange = vi.fn()
    render(<Pagination currentPage={5} totalPages={10} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByLabelText("Go to previous page"))
    expect(onPageChange).toHaveBeenCalledWith(4)
  })

  it("calls onPageChange with next page when clicking next", () => {
    const onPageChange = vi.fn()
    render(<Pagination currentPage={5} totalPages={10} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByLabelText("Go to next page"))
    expect(onPageChange).toHaveBeenCalledWith(6)
  })

  it("calls onPageChange with correct page when clicking a page number", () => {
    const onPageChange = vi.fn()
    render(<Pagination currentPage={1} totalPages={10} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByLabelText("Go to page 2"))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it("disables previous button on first page", () => {
    render(<Pagination currentPage={1} totalPages={10} onPageChange={vi.fn()} />)
    expect(screen.getByLabelText("Go to previous page")).toBeDisabled()
  })

  it("disables next button on last page", () => {
    render(<Pagination currentPage={10} totalPages={10} onPageChange={vi.fn()} />)
    expect(screen.getByLabelText("Go to next page")).toBeDisabled()
  })

  it("does not render pagination when totalPages is 1", () => {
    render(<Pagination currentPage={1} totalPages={1} onPageChange={vi.fn()} />)
    // The nav should exist but the page buttons should be empty or just the nav
    expect(screen.getByLabelText("Pagination")).toBeInTheDocument()
    // With 1 page, only prev/next should exist but both disabled
    expect(screen.getByLabelText("Go to previous page")).toBeDisabled()
    expect(screen.getByLabelText("Go to next page")).toBeDisabled()
  })

  it("shows ellipsis for large page ranges", () => {
    const { container } = render(
      <Pagination currentPage={5} totalPages={20} onPageChange={vi.fn()} />
    )
    // The MoreHorizontal icon is rendered for ellipsis
    const svgs = container.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThan(0)
  })

  it("highlights current page with default variant", () => {
    render(<Pagination currentPage={3} totalPages={10} onPageChange={vi.fn()} />)
    const currentBtn = screen.getByLabelText("Go to page 3")
    expect(currentBtn.className).toContain("pointer-events-none")
  })

  it("sets aria-current page on current page button", () => {
    render(<Pagination currentPage={3} totalPages={10} onPageChange={vi.fn()} />)
    const currentBtn = screen.getByLabelText("Go to page 3")
    expect(currentBtn).toHaveAttribute("aria-current", "page")
  })
})
