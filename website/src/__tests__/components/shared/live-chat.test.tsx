import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import { LiveChat } from "@/components/shared/live-chat"

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

const { sendMessageMock } = vi.hoisted(() => ({
  sendMessageMock: vi.fn(),
}))

vi.mock("@/api/endpoints", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/endpoints")>()
  return {
    ...actual,
    supportApi: { ...actual.supportApi, sendMessage: sendMessageMock },
  }
})

const sessionStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("sessionStorage", sessionStorageMock)
  sendMessageMock.mockResolvedValue({
    data: { conversation_id: "c-1", reply: "I can help with that!", escalated: false },
  })
})

describe("LiveChat (floating)", () => {
  it("renders the trigger button", () => {
    render(<LiveChat />)
    expect(screen.getByRole("button", { name: /ARGO Support/i })).toBeInTheDocument()
  })

  it("opens the panel and shows the welcome message", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    expect(screen.getByText(/Hi, I'm ARGO/i)).toBeInTheDocument()
  })

  it("sends a message and renders the assistant reply", async () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))

    const textarea = screen.getByPlaceholderText("Type your message...")
    fireEvent.change(textarea, { target: { value: "How do I reset a password?" } })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledWith({
        conversation_id: null,
        message: "How do I reset a password?",
        channel: "chat",
      })
    })
    expect(await screen.findByText("I can help with that!")).toBeInTheDocument()
  })

  it("persists the conversation id in sessionStorage", async () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "hello" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))
    await screen.findByText("I can help with that!")
    expect(sessionStorageMock.setItem).toHaveBeenCalledWith("operion-chat-conversation-id", "c-1")
  })

  it("shows an error bubble with retry when the API call fails", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("network"))
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    const retry = await screen.findByRole("button", { name: /Retry/i })
    expect(retry).toBeInTheDocument()
  })

  it("retries a failed message", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("network"))
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    const retry = await screen.findByRole("button", { name: /Retry/i })
    fireEvent.click(retry)

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByText("I can help with that!")).toBeInTheDocument()
  })

  it("closes the panel with the close button", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.click(screen.getByRole("button", { name: /Close/i }))
    expect(screen.queryByText(/Hi, I'm ARGO/i)).not.toBeInTheDocument()
  })

  it("closes the panel with the Escape key", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByText(/Hi, I'm ARGO/i)).not.toBeInTheDocument()
  })

  it("does not send empty messages", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "   " },
    })
    const send = screen.getByRole("button", { name: /Send/i }) as HTMLButtonElement
    expect(send.disabled).toBe(true)
  })

  it("sends on Enter without shift", async () => {
    const user = userEvent.setup()
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    const textarea = screen.getByPlaceholderText("Type your message...")
    await user.clear(textarea)
    await user.type(textarea, "enter message{Enter}")

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledTimes(1)
    })
  })

  it("attaches a file via the file input", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    const file = new File(["log"], "errors.log", { type: "text/plain" })
    fireEvent.click(screen.getByRole("button", { name: /Attach file/i }))
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    expect(screen.getByText("errors.log")).toBeInTheDocument()
  })

  it("removes a pending attachment", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    const file = new File(["log"], "errors.log", { type: "text/plain" })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole("button", { name: /Remove/i }))
    expect(screen.queryByText("errors.log")).not.toBeInTheDocument()
  })

  it("re-adds an error bubble when the retry also fails", async () => {
    sendMessageMock
      .mockRejectedValueOnce(new Error("boom"))
      .mockRejectedValueOnce(new Error("boom again"))
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    const retry = await screen.findByRole("button", { name: /Retry/i })
    fireEvent.click(retry)
    expect(
      await screen.findByText(/Something went wrong sending that/i)
    ).toBeInTheDocument()
  })

  it("closes the panel when the mobile backdrop is clicked", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    const backdrop = document.querySelector(".fixed.inset-0.z-40") as HTMLElement
    expect(backdrop).not.toBeNull()
    fireEvent.click(backdrop)
    expect(screen.queryByText(/Hi, I'm ARGO/i)).not.toBeInTheDocument()
  })

  it("closes the panel when clicking outside it", () => {
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    fireEvent.mouseDown(document.body)
    expect(screen.queryByText(/Hi, I'm ARGO/i)).not.toBeInTheDocument()
  })

  it("restores an existing conversation id from session storage", async () => {
    sessionStorageMock.getItem.mockReturnValueOnce("c-restored" as any)
    sendMessageMock.mockResolvedValue({
      data: { conversation_id: "c-restored", reply: "Welcome back!", escalated: false },
    })
    render(<LiveChat />)
    fireEvent.click(screen.getByRole("button", { name: /ARGO Support/i }))
    // No welcome message because a conversation already exists.
    expect(screen.queryByText(/Hi, I'm ARGO/i)).not.toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "hello" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledWith({
        conversation_id: "c-restored",
        message: "hello",
        channel: "chat",
      })
    })
  })
})

describe("LiveChat (embedded)", () => {
  it("renders the panel inline", () => {
    render(<LiveChat variant="embedded" />)
    expect(screen.getByText(/ARGO Support/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Minimize/i })).toBeInTheDocument()
  })

  it("minimizes the panel", () => {
    render(<LiveChat variant="embedded" />)
    fireEvent.click(screen.getByRole("button", { name: /Minimize/i }))
    expect(screen.queryByPlaceholderText("Type your message...")).not.toBeInTheDocument()
  })

  it("expands a minimized panel", () => {
    render(<LiveChat variant="embedded" />)
    fireEvent.click(screen.getByRole("button", { name: /Minimize/i }))
    fireEvent.click(screen.getByRole("button", { name: /Expand/i }))
    expect(screen.getByPlaceholderText("Type your message...")).toBeInTheDocument()
  })
})
