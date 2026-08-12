import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { Routes, Route } from "react-router"
import TutorialDetailPage from "@/pages/public/tutorial-detail"
import { useTutorial } from "@/services/queries"

const mockTutorial = {
  title: "Your First Route Plan: A Beginner's Guide",
  slug: "your-first-route-plan",
  category: "beginner",
  difficulty: "beginner",
  excerpt: "Learn how to create your first route plan",
  content: "Route planning is the core of Operion ERP",
  reading_time_minutes: 8,
  published_at: "2026-01-15",
  updated_at: "2026-06-01",
  tags: ["beginner", "route-planning"],
  author: { name: "Test Author" },
}

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
  })

  it("renders tutorial title", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: mockTutorial } as any)
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText("Your First Route Plan: A Beginner's Guide")).toBeInTheDocument()
  })

  it("shows category badge and difficulty level", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: mockTutorial } as any)
    renderWithRoute("your-first-route-plan")
    expect(screen.getAllByText("beginner").length).toBeGreaterThanOrEqual(1)
  })

  it("shows reading time", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: mockTutorial } as any)
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText("8 min read")).toBeInTheDocument()
  })

  it("shows article content", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: mockTutorial } as any)
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText(/Route planning is the core of Operion ERP/)).toBeInTheDocument()
  })

  it("has back link", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: mockTutorial } as any)
    renderWithRoute("your-first-route-plan")
    expect(screen.getByText("Back to Tutorials")).toBeInTheDocument()
  })

  it("shows not found state for invalid slug", () => {
    vi.mocked(useTutorial).mockReturnValue({ isLoading: false, data: undefined } as any)
    renderWithRoute("non-existent-tutorial")
    expect(screen.getByText("This tutorial does not exist.")).toBeInTheDocument()
    expect(screen.getByText("Back to Tutorials")).toBeInTheDocument()
  })
})
