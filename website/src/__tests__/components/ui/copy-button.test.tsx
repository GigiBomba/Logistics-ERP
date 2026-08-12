import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { CopyButton } from "@/components/ui/copy-button"

describe("CopyButton", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders with Copy label", () => {
    render(<CopyButton text="Hello" />)
    expect(screen.getByText("Copy")).toBeInTheDocument()
  })

  it("copies text to clipboard on click", async () => {
    render(<CopyButton text="Hello World" />)

    fireEvent.click(screen.getByRole("button"))

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Hello World")
    })
  })

  it("shows Copied! feedback after clicking", async () => {
    render(<CopyButton text="Hello" />)

    fireEvent.click(screen.getByRole("button"))

    await waitFor(() => {
      expect(screen.getByText("Copied!")).toBeInTheDocument()
    })
  })

  it("shows check icon after copying", async () => {
    render(<CopyButton text="Hello" />)

    fireEvent.click(screen.getByRole("button"))

    await waitFor(() => {
      const checkIcon = document.querySelector(".text-emerald-500")
      expect(checkIcon).toBeInTheDocument()
    })
  })

  it("resets to Copy after 2000ms", async () => {
    render(<CopyButton text="Hello" />)

    fireEvent.click(screen.getByRole("button"))

    await waitFor(() => {
      expect(screen.getByText("Copied!")).toBeInTheDocument()
    })

    // The component resets after 2000ms via setTimeout
    await waitFor(
      () => {
        expect(screen.getByText("Copy")).toBeInTheDocument()
      },
      { timeout: 4000 }
    )
  })
})
