import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import OnboardingPage from "@/pages/dashboard/onboarding"
import { useOnboardingChecklist, useTutorials, useChangelog } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useOnboardingChecklist: vi.fn(),
  useTutorials: vi.fn(),
  useChangelog: vi.fn(),
  useCompleteOnboardingStep: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    circle: ({ children, ...props }: any) => <circle {...props}>{children}</circle>,
  },
}))

const MOCK_STEPS = [
  { id: "verify-email", title: "Verify your email", description: "Confirm your email address.", completed: true, required: true },
  { id: "company-profile", title: "Set up company profile", description: "Add your company details.", completed: false, required: true },
  { id: "choose-plan", title: "Choose your plan", description: "Pick a subscription plan.", completed: false, required: true },
  { id: "download-desktop", title: "Download Operion Desktop", description: "Install the desktop app.", completed: false, required: false },
  { id: "first-route", title: "Create your first route", description: "Plan your first trip.", completed: false, required: false },
  { id: "add-members", title: "Add team members", description: "Invite your team.", completed: false, required: false },
  { id: "notifications", title: "Set up notifications", description: "Configure alerts.", completed: false, required: false },
  { id: "explore-docs", title: "Explore documentation", description: "Browse the docs.", completed: false, required: false },
]

const MOCK_TUTORIALS = [
  { id: 1, title: "Route Optimization 101", category: "beginner", reading_time_minutes: 5, excerpt: "Learn route planning basics." },
  { id: 2, title: "Dispatch Console Basics", category: "intermediate", reading_time_minutes: 15, excerpt: "Dispatch workflow overview." },
  { id: 3, title: "Fleet Analytics Overview", category: "advanced", reading_time_minutes: 10, excerpt: "Understand fleet metrics." },
  { id: 4, title: "API Integration Guide", category: "developer", reading_time_minutes: 20, excerpt: "Integrate with the Operion API." },
]

const MOCK_RELEASES = [
  { version: "1.2.0", release_date: "2026-08-01T00:00:00Z", sections: [{ type: "added", items: ["Fleet Analytics Dashboard", "Route performance insights"] }] },
  { version: "1.1.0", release_date: "2026-06-01T00:00:00Z", sections: [{ type: "added", items: ["Multi-warehouse Support", "Cross-dock improvements"] }] },
  { version: "1.0.0", release_date: "2026-04-01T00:00:00Z", sections: [{ type: "added", items: ["Operion GA Release", "Launch build"] }] },
]

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useOnboardingChecklist).mockReturnValue({
      data: { steps: MOCK_STEPS, completed_count: 1, total_count: 8 },
      isLoading: false,
      isError: false,
    } as any)
    vi.mocked(useTutorials).mockReturnValue({
      data: MOCK_TUTORIALS,
      isLoading: false,
      isError: false,
    } as any)
    vi.mocked(useChangelog).mockReturnValue({
      data: MOCK_RELEASES,
      isLoading: false,
      isError: false,
    } as any)
  })

  it('renders "Getting Started" heading and description', () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Getting Started")).toBeInTheDocument()
    expect(screen.getByText(/Complete these steps to set up your Operion account/i)).toBeInTheDocument()
  })

  it("shows overall progress section with percentage", () => {
    render(<OnboardingPage />)
    // 1 of 8 steps completed = 12.5% rounded to 13 or 12
    expect(screen.getByText(/%/)).toBeInTheDocument()
    expect(screen.getByText(/1 of 8 steps completed/i)).toBeInTheDocument()
  })

  it("shows required steps progress", () => {
    render(<OnboardingPage />)
    // 3 required steps, 1 completed (verify-email)
    expect(screen.getByText(/1 \/ 3 completed/i)).toBeInTheDocument()
  })

  it("shows Onboarding Checklist heading", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Onboarding Checklist")).toBeInTheDocument()
  })

  it("renders all 8 onboarding steps", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Verify your email")).toBeInTheDocument()
    expect(screen.getByText("Set up company profile")).toBeInTheDocument()
    expect(screen.getByText("Choose your plan")).toBeInTheDocument()
    expect(screen.getByText("Download Operion Desktop")).toBeInTheDocument()
    expect(screen.getByText("Create your first route")).toBeInTheDocument()
    expect(screen.getByText("Add team members")).toBeInTheDocument()
    expect(screen.getByText("Set up notifications")).toBeInTheDocument()
    expect(screen.getByText("Explore documentation")).toBeInTheDocument()
  })

  it("shows Done badge for completed step", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Done")).toBeInTheDocument()
  })

  it("shows Complete buttons for incomplete steps", () => {
    render(<OnboardingPage />)
    const completeButtons = screen.getAllByText("Complete")
    expect(completeButtons.length).toBe(7)
  })

  it("shows Required badge on required steps", () => {
    render(<OnboardingPage />)
    const requiredBadges = screen.getAllByText("Required")
    expect(requiredBadges.length).toBe(3)
  })

  it("shows step numbers", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Step 1")).toBeInTheDocument()
    expect(screen.getByText("Step 8")).toBeInTheDocument()
  })

  it("shows Recommended Tutorials section with all 4 tutorials", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Recommended Tutorials")).toBeInTheDocument()
    expect(screen.getByText("Route Optimization 101")).toBeInTheDocument()
    expect(screen.getByText("Dispatch Console Basics")).toBeInTheDocument()
    expect(screen.getByText("Fleet Analytics Overview")).toBeInTheDocument()
    expect(screen.getByText("API Integration Guide")).toBeInTheDocument()
  })

  it("shows tutorial levels and durations", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Beginner")).toBeInTheDocument()
    expect(screen.getByText("Intermediate")).toBeInTheDocument()
    expect(screen.getByText("Advanced")).toBeInTheDocument()
    expect(screen.getByText("Developer")).toBeInTheDocument()
    expect(screen.getByText("5 min")).toBeInTheDocument()
    expect(screen.getByText("15 min")).toBeInTheDocument()
  })

  it("shows Release Highlights section", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Release Highlights")).toBeInTheDocument()
    expect(screen.getByText("Fleet Analytics Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Multi-warehouse Support")).toBeInTheDocument()
    expect(screen.getByText("Operion GA Release")).toBeInTheDocument()
  })

  it("shows version badges on releases", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("v1.2.0")).toBeInTheDocument()
    expect(screen.getByText("v1.1.0")).toBeInTheDocument()
    expect(screen.getByText("v1.0.0")).toBeInTheDocument()
  })

  it("shows Best Practices section placeholder", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Best Practices")).toBeInTheDocument()
    expect(screen.getByText("Coming soon")).toBeInTheDocument()
  })

  it("shows Need help? callout with Contact Support link", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Need help?")).toBeInTheDocument()
    expect(screen.getByText("Contact Support")).toBeInTheDocument()
  })
})
