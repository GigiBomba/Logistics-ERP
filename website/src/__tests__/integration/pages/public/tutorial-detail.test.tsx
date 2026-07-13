import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { Routes, Route } from "react-router"
import TutorialDetailPage from "@/pages/public/tutorial-detail"
import { useTutorial } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useTutorial: vi.fn(),
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

function renderWithRoute(slug: string) {
  return render(
    <Routes>
      <Route path="/tutorials/:slug" element={<TutorialDetailPage />} />
    </Routes>,
    { initialEntries: [`/tutorials/${slug}`] }
  )
}

describe("TutorialDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTutorial).mockReturnValue({
      isLoading: false,
      data: undefined,
    } as any)
  })

  it("renders tutorial title", () => {
    renderWithRoute("your-first-route-plan")
    expect(
      screen.getByText("Your First Route Plan: A Beginner's Guide")
    ).toBeInTheDocument()
  })

  it("shows category badge and difficulty level", () => {
    renderWithRoute("your-first-route-plan")
    // Category and difficulty are both "Beginner" - appears in heading, badge, and tags
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(1)
  })

  it("shows reading time", () => {
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText("8 min read")).toBeInTheDocument()
  })

  it("shows article content", () => {
    renderWithRoute("your-first-route-plan")
    expect(
      screen.getByText(/Route planning is the core of Operion ERP/)
    ).toBeInTheDocument()
    // "Step 1: Prepare Your Data" appears in TOC sidebar AND article content
    expect(screen.getAllByText("Step 1: Prepare Your Data").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Step 2: Create a New Route").length).toBeGreaterThanOrEqual(1)
  })

  it("has back link and shows related tutorials", () => {
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText("Back to Tutorials")).toBeInTheDocument()
    expect(screen.getByText("Next Steps")).toBeInTheDocument()
    expect(
      screen.getByText("Continue learning with these related tutorials.")
    ).toBeInTheDocument()
  })

  it("shows tags and share section", () => {
    renderWithRoute("your-first-route-plan")
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("Share this tutorial")).toBeInTheDocument()
  })

  it("shows not found state for invalid slug", () => {
    renderWithRoute("non-existent-tutorial")
    expect(screen.getByText("This tutorial does not exist.")).toBeInTheDocument()
    expect(screen.getByText("Back to Tutorials")).toBeInTheDocument()
  })
})
