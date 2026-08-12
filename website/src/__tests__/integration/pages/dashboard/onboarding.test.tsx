import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import OnboardingPage from "@/pages/dashboard/onboarding"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    circle: ({ children, ...props }: any) => <circle {...props}>{children}</circle>,
  },
}))

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it("shows Best Practices section with 5 items", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Best Practices")).toBeInTheDocument()
    expect(screen.getByText(/Start with a small pilot fleet/i)).toBeInTheDocument()
    expect(screen.getByText(/Keep driver mobile apps updated/i)).toBeInTheDocument()
  })

  it("shows Need help? callout with Contact Support link", () => {
    render(<OnboardingPage />)
    expect(screen.getByText("Need help?")).toBeInTheDocument()
    expect(screen.getByText("Contact Support")).toBeInTheDocument()
  })
})
