import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import CampaignTab from "@/pages/admin/waitlist/campaign-tab"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("CampaignTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe("campaign display", () => {
    it("renders the campaign title with icon", () => {
      render(<CampaignTab />)
      expect(screen.getByText("Campaign Sending")).toBeInTheDocument()
    })

    it("renders the campaign description", () => {
      render(<CampaignTab />)
      expect(
        screen.getByText("Mass outreach to waitlist segments")
      ).toBeInTheDocument()
    })

    it("renders coming soon message", () => {
      render(<CampaignTab />)
      expect(
        screen.getByText(
          "Campaign sending will be available in the next release."
        )
      ).toBeInTheDocument()
    })

    it("renders coming soon description with details", () => {
      render(<CampaignTab />)
      expect(
        screen.getByText(
          "This feature will allow you to send targeted email campaigns to specific waitlist segments — for example, inviting a batch of users, re-engaging churned entries, or announcing product updates to activated accounts."
        )
      ).toBeInTheDocument()
    })
  })

  describe("layout", () => {
    it("renders within a card with max-width constraint", () => {
      const { container } = render(<CampaignTab />)
      // Find the outer card element
      const card = container.querySelector(".max-w-2xl")
      expect(card).toBeInTheDocument()
    })

    it("does not render any interactive controls", () => {
      render(<CampaignTab />)
      // Currently a static placeholder — no buttons, inputs, links
      expect(screen.queryByRole("button")).not.toBeInTheDocument()
      expect(screen.queryByRole("link")).not.toBeInTheDocument()
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    })
  })
})
