import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, mockAxiosResponse } from "@/test-utils"
import CampaignTab from "@/pages/admin/waitlist/campaign-tab"
import { waitlistApi } from "@/api/endpoints"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/api/endpoints", () => ({
  waitlistApi: {
    sendCampaign: vi.fn(),
  },
}))

describe("CampaignTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(waitlistApi.sendCampaign).mockResolvedValue(
      mockAxiosResponse({ status: "sent", count: 5, total_recipients: 5, errors: 0 })
    )
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
  })

  describe("campaign form", () => {
    it("renders subject input with label and placeholder", () => {
      render(<CampaignTab />)
      expect(screen.getByLabelText("Subject")).toBeInTheDocument()
      expect(
        screen.getByPlaceholderText("Enter email subject...")
      ).toBeInTheDocument()
    })

    it("renders message textarea with label and placeholder", () => {
      render(<CampaignTab />)
      expect(screen.getByLabelText("Email body")).toBeInTheDocument()
      expect(
        screen.getByPlaceholderText(
          "Write your email content here... Supports plain text."
        )
      ).toBeInTheDocument()
    })

    it("renders segment select with all status options", () => {
      render(<CampaignTab />)
      const select = screen.getByRole("combobox")
      expect(select).toBeInTheDocument()
      const options = screen.getAllByRole("option")
      expect(options.map((o) => o.textContent)).toEqual([
        "All statuses",
        "Joined",
        "Invited",
        "Activated",
        "Converted",
        "Churned",
        "Unsubscribed",
      ])
    })

    it("disables the Send button until subject and body are filled", () => {
      render(<CampaignTab />)
      const sendButton = screen.getByRole("button", { name: /Send Campaign/i })
      expect(sendButton).toBeDisabled()

      fireEvent.change(screen.getByLabelText("Subject"), {
        target: { value: "Big update" },
      })
      expect(sendButton).toBeDisabled()

      fireEvent.change(screen.getByLabelText("Email body"), {
        target: { value: "Hello everyone," },
      })
      expect(sendButton).toBeEnabled()
    })
  })

  describe("sending", () => {
    it("sends the campaign with subject, body and segment on success", async () => {
      render(<CampaignTab />)
      fireEvent.change(screen.getByLabelText("Subject"), {
        target: { value: "Big update" },
      })
      fireEvent.change(screen.getByLabelText("Email body"), {
        target: { value: "Hello everyone," },
      })
      fireEvent.change(screen.getByRole("combobox"), {
        target: { value: "joined" },
      })

      fireEvent.click(screen.getByRole("button", { name: /Send Campaign/i }))

      await waitFor(() => {
        expect(waitlistApi.sendCampaign).toHaveBeenCalledWith({
          subject: "Big update",
          body: "Hello everyone,",
          segment: "joined",
        })
      })
      expect(await screen.findByText("Campaign sent")).toBeInTheDocument()
      expect(
        screen.getByText(/Sent to 5 of 5 recipients/)
      ).toBeInTheDocument()
    })

    it("shows error feedback when sending fails", async () => {
      vi.mocked(waitlistApi.sendCampaign).mockRejectedValue(
        new Error("Network error")
      )
      render(<CampaignTab />)
      fireEvent.change(screen.getByLabelText("Subject"), {
        target: { value: "Big update" },
      })
      fireEvent.change(screen.getByLabelText("Email body"), {
        target: { value: "Hello everyone," },
      })
      fireEvent.click(screen.getByRole("button", { name: /Send Campaign/i }))

      expect(await screen.findByText("Send failed")).toBeInTheDocument()
      expect(screen.getByText("Network error")).toBeInTheDocument()
    })

    it("shows no-recipients feedback when the segment is empty", async () => {
      vi.mocked(waitlistApi.sendCampaign).mockResolvedValue(
        mockAxiosResponse({ status: "no_recipients", count: 0, total_recipients: 0, errors: 0 })
      )
      render(<CampaignTab />)
      fireEvent.change(screen.getByLabelText("Subject"), {
        target: { value: "Big update" },
      })
      fireEvent.change(screen.getByLabelText("Email body"), {
        target: { value: "Hello everyone," },
      })
      fireEvent.click(screen.getByRole("button", { name: /Send Campaign/i }))

      expect(await screen.findByText("No recipients")).toBeInTheDocument()
      expect(
        screen.getByText("No waitlist entries match the selected segment.")
      ).toBeInTheDocument()
    })
  })
})