import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { NewsletterForm } from "@/components/shared/newsletter-form"

vi.mock("motion/react", () => {
  const MotionComponent = (props: any) => {
    const { children, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    motion: new Proxy(
      {},
      {
        get: () => MotionComponent,
      }
    ),
    AnimatePresence: ({ children }: any) => <>{children}</>,
  }
})

vi.mock("@/i18n/locale-context", async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useLocale: () => ({
      t: (key: string) => key,
    }),
  }
})

// Track whether toast.success was called
const mockToastSuccess = vi.fn()
vi.mock("sonner", () => ({
  toast: { success: (...args: any[]) => mockToastSuccess(...args) },
}))

describe("NewsletterForm", () => {
  beforeEach(() => {
    mockToastSuccess.mockReset()
  })

  describe("card variant (default)", () => {
    it("renders email input and subscribe button", () => {
      render(<NewsletterForm />)
      expect(screen.getByLabelText("newsletter.placeholder")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: "newsletter.subscribe" })).toBeInTheDocument()
    })

    it("renders the card title and description", () => {
      render(<NewsletterForm />)
      expect(screen.getByText("newsletter.title")).toBeInTheDocument()
      expect(screen.getByText("newsletter.desc")).toBeInTheDocument()
    })

    it("renders preference checkboxes", () => {
      render(<NewsletterForm />)
      expect(screen.getByText("Product Updates")).toBeInTheDocument()
      expect(screen.getByText("Blog Digest")).toBeInTheDocument()
      expect(screen.getByText("Event Invites")).toBeInTheDocument()
    })

    it("checks Product Updates by default", () => {
      render(<NewsletterForm />)
      const productCheckbox = screen.getByLabelText("Product Updates") as HTMLInputElement
      expect(productCheckbox.checked).toBe(true)
    })

    it("does not check Blog Digest by default", () => {
      render(<NewsletterForm />)
      const blogCheckbox = screen.getByLabelText("Blog Digest") as HTMLInputElement
      expect(blogCheckbox.checked).toBe(false)
    })

    it("toggles preference on checkbox click", () => {
      render(<NewsletterForm />)
      const blogCheckbox = screen.getByLabelText("Blog Digest") as HTMLInputElement
      fireEvent.click(blogCheckbox)
      expect(blogCheckbox.checked).toBe(true)
      fireEvent.click(blogCheckbox)
      expect(blogCheckbox.checked).toBe(false)
    })

    it("disables submit button when email is empty", () => {
      render(<NewsletterForm />)
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      expect(button).toBeDisabled()
    })

    it("enables submit button when email is entered", () => {
      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      expect(button).not.toBeDisabled()
    })

    it("shows success state after successful submission", async () => {
      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      fireEvent.click(button)
      await waitFor(() => {
        expect(screen.getByText("newsletter.success")).toBeInTheDocument()
      })
    })

    it("calls toast.success on successful submission", async () => {
      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      fireEvent.click(button)
      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith("newsletter.success")
      })
    })

    it("shows error message when submission fails", async () => {
      // Make toast.success throw synchronously to trigger the error path
      mockToastSuccess.mockImplementationOnce(() => {
        throw new Error("Network error")
      })

      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      fireEvent.click(button)
      await waitFor(() => {
        expect(screen.getByText("newsletter.error")).toBeInTheDocument()
      })
    })

    it("transitions to success state after submission", async () => {
      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      expect(button).not.toBeDisabled()
      fireEvent.click(button)

      // The form is replaced by a success message (card variant)
      await waitFor(() => {
        expect(screen.getByText("newsletter.success")).toBeInTheDocument()
      })
      // The subscribe button should no longer be in the DOM
      expect(screen.queryByRole("button", { name: "newsletter.subscribe" })).not.toBeInTheDocument()
    })

    it("renders the preferences fieldset legend", () => {
      render(<NewsletterForm />)
      expect(screen.getByText("newsletter.preferences")).toBeInTheDocument()
    })
  })

  describe("inline variant", () => {
    it("renders inline form with email input and subscribe button", () => {
      render(<NewsletterForm variant="inline" />)
      expect(screen.getByLabelText("newsletter.placeholder")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: "newsletter.subscribe" })).toBeInTheDocument()
    })

    it("shows success state with inline success message", async () => {
      render(<NewsletterForm variant="inline" />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      fireEvent.click(button)
      await waitFor(() => {
        // The inline success message combines success + checkEmail in one <p>
        expect(screen.getByText(/newsletter\.success/)).toBeInTheDocument()
      })
    })
  })

  describe("footer variant", () => {
    it("renders footer form with description, input and subscribe button", () => {
      render(<NewsletterForm variant="footer" />)
      expect(screen.getByText("newsletter.desc")).toBeInTheDocument()
      expect(screen.getByLabelText("newsletter.placeholder")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: "newsletter.subscribe" })).toBeInTheDocument()
    })

    it("shows success state with footer success message", async () => {
      render(<NewsletterForm variant="footer" />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "test@example.com" } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      fireEvent.click(button)
      await waitFor(() => {
        // The footer success message combines success + checkEmail in one <p>
        expect(screen.getByText(/newsletter\.success/)).toBeInTheDocument()
      })
    })
  })

  describe("validation", () => {
    it("does not submit when email is empty", () => {
      render(<NewsletterForm />)
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      expect(button).toBeDisabled()
    })

    it("does not submit when email contains only whitespace", () => {
      render(<NewsletterForm />)
      const input = screen.getByLabelText("newsletter.placeholder")
      fireEvent.change(input, { target: { value: "   " } })
      const button = screen.getByRole("button", { name: "newsletter.subscribe" })
      expect(button).toBeDisabled()
    })
  })

  describe("className forwarding", () => {
    it("forwards className to the card container", () => {
      const { container } = render(<NewsletterForm className="custom-class" />)
      const card = container.querySelector(".custom-class")
      expect(card).toBeInTheDocument()
    })

    it("forwards className to inline variant", () => {
      const { container } = render(<NewsletterForm variant="inline" className="custom-inline" />)
      const form = container.querySelector(".custom-inline")
      expect(form).toBeInTheDocument()
    })
  })
})
