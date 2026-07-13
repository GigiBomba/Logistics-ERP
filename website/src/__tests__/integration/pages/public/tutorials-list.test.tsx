import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import TutorialsListPage from "@/pages/public/tutorials-list"
import { useTutorials } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useTutorials: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("TutorialsListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTutorials).mockReturnValue({
      isLoading: false,
      data: undefined,
    } as any)
  })

  it("renders 'Tutorials' heading", () => {
    render(<TutorialsListPage />)
    expect(screen.getByText("Tutorials")).toBeInTheDocument()
  })

  it("shows search input", () => {
    render(<TutorialsListPage />)
    expect(screen.getByPlaceholderText("Search tutorials...")).toBeInTheDocument()
  })

  it("shows category filter tabs", () => {
    render(<TutorialsListPage />)
    expect(screen.getByText("All")).toBeInTheDocument()
    // "Beginner" appears as tab, category badge, AND difficulty badge
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Advanced").length).toBeGreaterThanOrEqual(1)
    // "Administrator" appears as tab AND category badge
    expect(screen.getAllByText("Administrator").length).toBeGreaterThanOrEqual(1)
    // "Dispatcher" appears as both tab and category badge
    expect(screen.getAllByText("Dispatcher").length).toBeGreaterThanOrEqual(1)
    // "Fleet Manager" appears as both tab and category badge
    expect(screen.getAllByText("Fleet Manager").length).toBeGreaterThanOrEqual(1)
    // "Driver" appears as both tab and category badge
    expect(screen.getAllByText("Driver").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Installation").length).toBeGreaterThanOrEqual(1)
    // "AI Assistant" appears as both tab and category badge
    expect(screen.getAllByText("AI Assistant").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("OCR").length).toBeGreaterThanOrEqual(1)
    // "Analytics" appears as both tab and category badge
    expect(screen.getAllByText("Analytics").length).toBeGreaterThanOrEqual(1)
  })

  it("renders tutorial cards with category badges", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText("Fleet Manager").length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText("Dispatcher").length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText("AI Assistant").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Analytics").length).toBeGreaterThanOrEqual(2)
  })

  it("shows difficulty level badges", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Advanced").length).toBeGreaterThanOrEqual(1)
  })

  it("shows reading time", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText(/12 min read/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/8 min read/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/15 min read/).length).toBeGreaterThanOrEqual(1)
  })

  it("shows tutorial count", () => {
    render(<TutorialsListPage />)
    // The count is rendered as "15" (number) followed by " tutorials" — split across text nodes
    // Use a function matcher to catch the combined text
    expect(
      screen.getByText((content) => content.includes("15") && content.includes("tutorial"))
    ).toBeInTheDocument()
  })
})
