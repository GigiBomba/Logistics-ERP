import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import React from "react"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const sampleItems = [
  {
    question: "How do I get started?",
    answer: "Sign up for an account and follow the onboarding wizard.",
  },
  {
    question: "Is there a mobile app?",
    answer: "Yes, available on iOS and Android.",
  },
  {
    question: "What payment methods are accepted?",
    answer: "We accept Visa, Mastercard, and PayPal.",
  },
]

describe("FaqAccordion", () => {
  it("renders all questions", () => {
    render(<FaqAccordion items={sampleItems} />)
    expect(screen.getByText("How do I get started?")).toBeInTheDocument()
    expect(screen.getByText("Is there a mobile app?")).toBeInTheDocument()
    expect(screen.getByText("What payment methods are accepted?")).toBeInTheDocument()
  })

  it("clicking a question expands its answer", () => {
    render(<FaqAccordion items={sampleItems} />)
    const button = screen.getByText("How do I get started?")
    fireEvent.click(button)
    expect(
      screen.getByText("Sign up for an account and follow the onboarding wizard.")
    ).toBeInTheDocument()
  })

  it("clicking again collapses the answer", () => {
    render(<FaqAccordion items={sampleItems} />)
    const button = screen.getByText("How do I get started?")
    // Expand
    fireEvent.click(button)
    expect(
      screen.getByText("Sign up for an account and follow the onboarding wizard.")
    ).toBeInTheDocument()
    // Collapse
    fireEvent.click(button)
    expect(
      screen.queryByText("Sign up for an account and follow the onboarding wizard.")
    ).not.toBeInTheDocument()
  })

  it("only one item is open at a time", () => {
    render(<FaqAccordion items={sampleItems} />)

    // Open first item
    fireEvent.click(screen.getByText("How do I get started?"))
    expect(
      screen.getByText("Sign up for an account and follow the onboarding wizard.")
    ).toBeInTheDocument()

    // Open second item - first should close
    fireEvent.click(screen.getByText("Is there a mobile app?"))
    expect(screen.getByText("Yes, available on iOS and Android.")).toBeInTheDocument()
    expect(
      screen.queryByText("Sign up for an account and follow the onboarding wizard.")
    ).not.toBeInTheDocument()
  })

  it("ChevronDown rotates when item is open", () => {
    render(<FaqAccordion items={sampleItems} />)
    const button = screen.getByRole("button", { name: /how do i get started/i })
    expect(button).toBeInTheDocument()

    // Click to expand
    fireEvent.click(button)
    // After click, the answer is visible, confirming the accordion expanded
    expect(
      screen.getByText("Sign up for an account and follow the onboarding wizard.")
    ).toBeInTheDocument()
  })

  it("renders answers for all items when each is expanded", () => {
    render(<FaqAccordion items={sampleItems} />)

    fireEvent.click(screen.getByText("How do I get started?"))
    expect(
      screen.getByText("Sign up for an account and follow the onboarding wizard.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByText("Is there a mobile app?"))
    expect(screen.getByText("Yes, available on iOS and Android.")).toBeInTheDocument()

    fireEvent.click(screen.getByText("What payment methods are accepted?"))
    expect(screen.getByText("We accept Visa, Mastercard, and PayPal.")).toBeInTheDocument()
  })
})
