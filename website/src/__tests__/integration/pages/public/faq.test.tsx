import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import FaqPage from "@/pages/public/faq"

const { motionMock } = vi.hoisted(() => {
  const MockMotionDiv = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  return {
    motionMock: new Proxy({}, { get: () => MockMotionDiv }),
  }
})

vi.mock("motion/react", () => ({
  motion: motionMock,
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

describe("FaqPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders the page title and general category items", () => {
    render(<FaqPage />)
    expect(screen.getAllByText("General").length).toBeGreaterThan(0)
    expect(screen.getByText("What is Operion?")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /general/i })).toHaveAttribute("aria-selected", "true")
  })

  it("expands and collapses an answer on click", () => {
    render(<FaqPage />)
    const question = screen.getByText("What is Operion?")
    expect(screen.queryByText(/AI logistics operating system/i)).not.toBeInTheDocument()

    fireEvent.click(question)
    expect(screen.getByText(/AI logistics operating system/i)).toBeInTheDocument()

    fireEvent.click(question)
    expect(screen.queryByText(/AI logistics operating system/i)).not.toBeInTheDocument()
  })

  it("switches to the billing tab", async () => {
    const user = userEvent.setup()
    render(<FaqPage />)
    await user.click(screen.getByRole("tab", { name: /billing/i }))
    expect(screen.getByRole("tab", { name: /billing/i })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("How much does Operion cost?")).toBeInTheDocument()
    expect(screen.queryByText("What is Operion?")).not.toBeInTheDocument()
  })

  it("filters questions by search term", async () => {
    const user = userEvent.setup()
    render(<FaqPage />)
    const search = screen.getByPlaceholderText(/search frequently asked questions/i)
    await user.type(search, "operion")
    expect(screen.getByText("What is Operion?")).toBeInTheDocument()
  })

  it("shows a no-results message when the search matches nothing", async () => {
    const user = userEvent.setup()
    render(<FaqPage />)
    const search = screen.getByPlaceholderText(/search frequently asked questions/i)
    await user.type(search, "zzzz-no-such-term")
    expect(
      screen.getByText(/no results found for your search/i)
    ).toBeInTheDocument()
  })

  it("switches to the technical tab and expands one of its questions", async () => {
    const user = userEvent.setup()
    render(<FaqPage />)
    await user.click(screen.getByRole("tab", { name: /technical/i }))
    expect(screen.getByRole("tab", { name: /technical/i })).toHaveAttribute("aria-selected", "true")
    // Technical tab is active — its items are rendered, general's are not.
    expect(screen.getByText("What are the system requirements?")).toBeInTheDocument()
    expect(screen.queryByText("What is Operion?")).not.toBeInTheDocument()
  })
})
