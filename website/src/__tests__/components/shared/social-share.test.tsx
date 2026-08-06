import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { SocialShare } from "@/components/shared/social-share"

const testUrl = "https://operionerp.xyz/blog/test"
const testTitle = "Test Article"

describe("SocialShare", () => {
  let openSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    openSpy = vi.spyOn(window, "open").mockImplementation(() => null)
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it("renders all default share buttons", () => {
    render(<SocialShare url={testUrl} title={testTitle} />)
    expect(screen.getByRole("button", { name: /share on x \(twitter\)/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /share on linkedin/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /share on facebook/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /share on whatsapp/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /copy link/i })).toBeInTheDocument()
  })

  it("renders only specified platforms", () => {
    render(
      <SocialShare url={testUrl} title={testTitle} platforms={["twitter", "copy"]} />
    )
    expect(screen.getByRole("button", { name: /share on x \(twitter\)/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /copy link/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /share on linkedin/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /share on facebook/i })).not.toBeInTheDocument()
  })

  it("copies URL to clipboard when copy button is clicked", async () => {
    render(<SocialShare url={testUrl} title={testTitle} />)

    const copyButton = screen.getByRole("button", { name: /copy link/i })
    fireEvent.click(copyButton)

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(testUrl)
    })
  })

  it("opens Twitter share URL with correct parameters", () => {
    render(<SocialShare url={testUrl} title={testTitle} />)

    const twitterButton = screen.getByRole("button", { name: /share on x \(twitter\)/i })
    fireEvent.click(twitterButton)

    const expectedUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(testTitle)}&url=${encodeURIComponent(testUrl)}`
    expect(openSpy).toHaveBeenCalledWith(expectedUrl, "_blank", "noopener,noreferrer")
  })

  it("opens LinkedIn share URL with correct parameters", () => {
    render(<SocialShare url={testUrl} title={testTitle} />)

    const linkedinButton = screen.getByRole("button", { name: /share on linkedin/i })
    fireEvent.click(linkedinButton)

    const expectedUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(testUrl)}&title=${encodeURIComponent(testTitle)}`
    expect(openSpy).toHaveBeenCalledWith(expectedUrl, "_blank", "noopener,noreferrer")
  })

  it("opens Facebook share URL with correct parameters", () => {
    render(<SocialShare url={testUrl} title={testTitle} />)

    const facebookButton = screen.getByRole("button", { name: /share on facebook/i })
    fireEvent.click(facebookButton)

    const expectedUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(testUrl)}`
    expect(openSpy).toHaveBeenCalledWith(expectedUrl, "_blank", "noopener,noreferrer")
  })

  it("opens WhatsApp share URL with title and url combined", () => {
    render(<SocialShare url={testUrl} title={testTitle} />)

    const whatsappButton = screen.getByRole("button", { name: /share on whatsapp/i })
    fireEvent.click(whatsappButton)

    const expectedUrl = `https://wa.me/?text=${encodeURIComponent(`${testTitle} ${testUrl}`)}`
    expect(openSpy).toHaveBeenCalledWith(expectedUrl, "_blank", "noopener,noreferrer")
  })
})
