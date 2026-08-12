import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { GlobalSearch } from "@/components/shared/global-search"

vi.mock("motion/react", () => {
  const MotionComponent = (props: any) => {
    const { children, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    motion: new Proxy(
      {},
      {
        get: () => MotionComponent,
      }
    ),
    AnimatePresence: ({ children }: any) => <>{children}</>,
  }
})

const mockNavigate = vi.fn()

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock("@/i18n/locale-context", async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useLocale: () => ({
      t: (key: string) => key,
    }),
  }
})

describe("GlobalSearch", () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    localStorage.clear()
    vi.useRealTimers()
  })

  it("renders search input when open", () => {
    render(<GlobalSearch open />)
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("does not render when closed", () => {
    render(<GlobalSearch open={false} />)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
  })

  it("shows quick actions when query is empty and search is open", () => {
    render(<GlobalSearch open />)
    expect(screen.getByText("search.quickActions")).toBeInTheDocument()
    expect(screen.getByText("search.quickActionDashboard")).toBeInTheDocument()
    expect(screen.getByText("search.quickActionDownload")).toBeInTheDocument()
  })

  it("displays search history from localStorage when present", () => {
    localStorage.setItem(
      "operion-search-history",
      JSON.stringify(["route planning", "api docs"])
    )
    render(<GlobalSearch open />)
    expect(screen.getByText("route planning")).toBeInTheDocument()
    expect(screen.getByText("api docs")).toBeInTheDocument()
    expect(screen.getByText("search.recentSearches")).toBeInTheDocument()
  })

  it("updates query on input change", () => {
    render(<GlobalSearch open />)
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "pricing" } })
    expect(input).toHaveValue("pricing")
  })

  it("shows no-results state with suggestions after typing a query", async () => {
    render(<GlobalSearch open />)
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "nonexistent" } })
    // Advance past the 300ms debounce and flush React renders
    vi.advanceTimersByTime(300)
    // Use waitFor to allow React to re-render after debounced state update
    await vi.waitFor(() => {
      expect(screen.getByText("common.noResults")).toBeInTheDocument()
    })
    expect(screen.getByText("search.tryDifferent")).toBeInTheDocument()
    // Suggestion buttons should be rendered
    expect(screen.getByText("Getting started guide")).toBeInTheDocument()
    expect(screen.getByText("Pricing plans")).toBeInTheDocument()
  })

  it("calls navigate when a quick action is selected", () => {
    render(<GlobalSearch open />)
    const dashboardAction = screen.getByText("search.quickActionDashboard")
    fireEvent.click(dashboardAction)
    expect(mockNavigate).toHaveBeenCalledWith("/dashboard")
  })

  it("calls navigate when a suggestion button is clicked", async () => {
    render(<GlobalSearch open />)
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "xyz" } })
    vi.advanceTimersByTime(300)
    await vi.waitFor(() => {
      expect(screen.getByText("Getting started guide")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText("Getting started guide"))
    expect(mockNavigate).toHaveBeenCalledWith("/docs/getting-started")
  })

  it("closes the modal when clicking the backdrop", () => {
    const onOpenChange = vi.fn()
    render(<GlobalSearch open onOpenChange={onOpenChange} />)
    const backdrop = document.querySelector('[aria-hidden="true"]')
    expect(backdrop).toBeInTheDocument()
    fireEvent.click(backdrop!)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("closes the modal on Escape keydown", () => {
    const onOpenChange = vi.fn()
    render(<GlobalSearch open onOpenChange={onOpenChange} />)
    fireEvent.keyDown(document, { key: "Escape" })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("moves selection with arrow keys", () => {
    render(<GlobalSearch open />)
    // Press ArrowDown on the dialog to select the first item
    const dialog = screen.getByRole("dialog")
    fireEvent.keyDown(dialog, { key: "ArrowDown" })
    // The first quick action button should receive selected styling (bg-accent)
    const dashboardBtn = screen.getByText("search.quickActionDashboard").closest("button")!
    expect(dashboardBtn.className).toContain("bg-accent")
  })

  it("stores search query in history after selection", async () => {
    render(<GlobalSearch open />)
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "pricing" } })
    vi.advanceTimersByTime(300)
    // Wait for suggestions to appear after debounce
    await vi.waitFor(() => {
      expect(screen.getByText("Pricing plans")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText("Pricing plans"))
    const history = JSON.parse(localStorage.getItem("operion-search-history") ?? "[]")
    expect(history).toContain("pricing")
  })

  it("does not render search history when localStorage is empty", () => {
    render(<GlobalSearch open />)
    expect(screen.queryByText("search.recentSearches")).not.toBeInTheDocument()
  })

  it("renders the dialog with aria-modal and aria-label", () => {
    render(<GlobalSearch open />)
    const dialog = screen.getByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(dialog.getAttribute("aria-modal")).toBe("true")
    expect(dialog.getAttribute("aria-label")).toBe("common.aria.search")
  })
})
