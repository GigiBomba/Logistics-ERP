import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import FaqPage from "@/pages/public/faq"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/components/seo/structured-data", () => ({
  JsonLd: () => null,
  faqSchema: vi.fn(() => ({})),
}))

describe("FaqPage", () => {
  it("renders the page title", () => {
    render(<FaqPage />)
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
  })

  it("renders the search input with placeholder text", () => {
    render(<FaqPage />)
    // faq.searchPlaceholder key not translated, renders as the key itself
    expect(
      screen.getByPlaceholderText("faq.searchPlaceholder")
    ).toBeInTheDocument()
  })

  it("renders category tabs with locale text", () => {
    render(<FaqPage />)
    expect(screen.getByRole("tab", { name: /General/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Billing/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Technical/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Security/i })).toBeInTheDocument()
  })

  it("renders the subtitle fallback text", () => {
    render(<FaqPage />)
    expect(screen.getByText("faq.subtitle")).toBeInTheDocument()
  })

  it("renders General tab content by default showing locale key questions", () => {
    render(<FaqPage />)
    expect(screen.getByText("faq.general1.q")).toBeInTheDocument()
    expect(screen.getByText("faq.general2.q")).toBeInTheDocument()
  })

  it("expands and shows answer when clicking a question", () => {
    render(<FaqPage />)
    const question = screen.getByText("faq.general1.q")
    const card = question.closest("[class*='cursor-pointer']") || question.parentElement
    fireEvent.click(card || question)
    expect(screen.getByText("faq.general1.a")).toBeInTheDocument()
  })

  it("can toggle multiple questions independently", () => {
    render(<FaqPage />)
    // Open first question
    const q1 = screen.getByText("faq.general1.q")
    fireEvent.click(q1.closest("[class*='cursor-pointer']") || q1)
    expect(screen.getByText("faq.general1.a")).toBeInTheDocument()
    // Open second question while first stays open
    const q2 = screen.getByText("faq.general2.q")
    fireEvent.click(q2.closest("[class*='cursor-pointer']") || q2)
    expect(screen.getByText("faq.general2.a")).toBeInTheDocument()
    // First answer should still be visible (multi-open accordion)
    expect(screen.getByText("faq.general1.a")).toBeInTheDocument()
  })

  it("switches category tab and shows billing questions", () => {
    render(<FaqPage />)
    fireEvent.click(screen.getByRole("tab", { name: /Billing/i }))
    expect(screen.getByText("faq.billing1.q")).toBeInTheDocument()
  })

  it("shows category item count badge in heading", () => {
    render(<FaqPage />)
    // Each category tab shows a badge with item count
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("filters questions by search query", () => {
    render(<FaqPage />)
    const searchInput = screen.getByPlaceholderText("faq.searchPlaceholder")
    fireEvent.change(searchInput, { target: { value: "general1" } })
    expect(screen.getByText("faq.general1.q")).toBeInTheDocument()
    expect(screen.queryByText("faq.general2.q")).not.toBeInTheDocument()
  })

  it("shows no results message when search matches nothing", () => {
    render(<FaqPage />)
    const searchInput = screen.getByPlaceholderText("faq.searchPlaceholder")
    fireEvent.change(searchInput, { target: { value: "xyznonexistent" } })
    expect(
      screen.getByText("No results found for your search. Try a different term.")
    ).toBeInTheDocument()
  })

  it("renders the 'Still Have Questions?' section", () => {
    render(<FaqPage />)
    expect(screen.getByText("Still Have Questions?")).toBeInTheDocument()
    expect(screen.getByText("Contact Support")).toBeInTheDocument()
  })

  it("renders contact support link pointing to /contact", () => {
    render(<FaqPage />)
    const link = screen.getByRole("link", { name: /contact support/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/contact")
  })

  it("renders canonical link", () => {
    render(<FaqPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/faq")
  })
})
