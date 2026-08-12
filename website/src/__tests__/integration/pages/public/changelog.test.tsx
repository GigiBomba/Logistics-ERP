import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import ChangelogPage from "@/pages/public/changelog"

vi.mock("@/api/endpoints", () => ({
  changelogApi: {
    getEntries: vi.fn().mockResolvedValue({
      data: [
        {
          version: "1.0.0",
          release_date: "2026-09-01",
          sections: [
            { type: "added" as const, items: ["Initial route planning module", "Fleet management dashboard"] },
            { type: "changed" as const, items: ["Updated UI components"] },
            { type: "fixed" as const, items: ["Bug fix in dispatch"] },
          ],
        },
        {
          version: "0.9.0",
          release_date: "2026-08-15",
          sections: [
            { type: "added" as const, items: ["Beta feature X"] },
            { type: "fixed" as const, items: ["Stability improvements"] },
          ],
        },
      ],
    }),
  },
  authApi: { getMe: vi.fn(), updateProfile: vi.fn(), changePassword: vi.fn() },
  subscriptionApi: { getCurrent: vi.fn(), getPlans: vi.fn() },
  companyApi: { get: vi.fn(), update: vi.fn() },
  supportApi: { createTicket: vi.fn(), getTickets: vi.fn() },
  blogApi: { getPosts: vi.fn(), getPost: vi.fn(), getCategories: vi.fn() },
  roadmapApi: { getItems: vi.fn() },
  statusApi: { getStatus: vi.fn() },
  tutorialsApi: { getTutorials: vi.fn(), getTutorial: vi.fn() },
  developersApi: { getResources: vi.fn(), getToolkitVersions: vi.fn() },
  securityApi: { getReports: vi.fn(), submitReport: vi.fn() },
  announcementsApi: { getAnnouncements: vi.fn() },
  invoicesApi: { getInvoices: vi.fn() },
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe("ChangelogPage", () => {
  it("renders Changelog heading", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("Changelog")).toBeInTheDocument()
  })

  it("renders release version items", async () => {
    render(<ChangelogPage />)
    expect(await screen.findByText("v1.0.0")).toBeInTheDocument()
    expect(screen.getByText("v0.9.0")).toBeInTheDocument()
  })

  it("renders release section titles for the first release", async () => {
    render(<ChangelogPage />)
    const addedEls = await screen.findAllByText("added")
    expect(addedEls.length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("changed").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("fixed").length).toBeGreaterThanOrEqual(1)
  })

  it("renders release date for version 1.0.0", async () => {
    render(<ChangelogPage />)
    expect(await screen.findByText(/September 1, 2026/)).toBeInTheDocument()
  })
})
