import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { SupportModal } from "@/components/shared/support-modal"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () =>
        ({ children, initial, animate, exit, transition, variants, whileInView, viewport, ...rest }: any) =>
          <div {...rest}>{children}</div>,
    }
  ),
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

const { useCreateTicketMock } = vi.hoisted(() => ({
  useCreateTicketMock: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useCreateTicket: useCreateTicketMock,
}))

const sessionStorageMock = {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0,
}

function mockTicketMutation(overrides: Partial<Record<string, any>> = {}) {
  useCreateTicketMock.mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    isError: false,
    ...overrides,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("sessionStorage", sessionStorageMock)
  sendMessageMock.mockResolvedValue({
    data: { conversation_id: "c-1", reply: "Let me check that for you.", escalated: false },
  })
  mockTicketMutation()
})

describe("SupportModal", () => {
  it("renders nothing when closed and uncontrolled", () => {
    render(<SupportModal />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders the dialog when controlled open", () => {
    render(<SupportModal open />)
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText(/ARGO Support/i)).toBeInTheDocument()
    expect(screen.getByText(/Hi, I'm ARGO/i)).toBeInTheDocument()
  })

  it("closes via the close button and notifies onOpenChange", () => {
    const onOpenChange = vi.fn()
    render(<SupportModal open onOpenChange={onOpenChange} />)
    fireEvent.click(screen.getByRole("button", { name: /Close/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("closes on Escape", () => {
    const onOpenChange = vi.fn()
    render(<SupportModal open onOpenChange={onOpenChange} />)
    fireEvent.keyDown(document, { key: "Escape" })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("sends a chat message and renders the reply", async () => {
    render(<SupportModal open />)
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "Where is my invoice?" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledWith({
        conversation_id: null,
        message: "Where is my invoice?",
        channel: "chat",
      })
    })
    expect(await screen.findByText("Let me check that for you.")).toBeInTheDocument()
  })

  it("shows an error bubble when sending fails", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("boom"))
    render(<SupportModal open />)
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))
    expect(await screen.findByRole("button", { name: /Retry/i })).toBeInTheDocument()
  })

  it("retries a failed chat message", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("boom"))
    render(<SupportModal open />)
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))
    const retry = await screen.findByRole("button", { name: /Retry/i })
    fireEvent.click(retry)
    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledTimes(2)
    })
  })

  it("switches to the ticket tab and submits a ticket", async () => {
    render(<SupportModal open />)
    fireEvent.click(screen.getByRole("button", { name: /Submit Ticket/i }))

    fireEvent.change(screen.getByLabelText(/Title/i), {
      target: { value: "Scanner offline" },
    })
    fireEvent.change(screen.getByLabelText(/Description/i), {
      target: { value: "The scanner keeps disconnecting." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    expect(await screen.findByText("Ticket submitted")).toBeInTheDocument()
  })

  it("does not submit a ticket with empty fields", () => {
    render(<SupportModal open />)
    fireEvent.click(screen.getByRole("button", { name: /Submit Ticket/i }))
    const submit = screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
  })

  it("shows the submit-another flow after a ticket", async () => {
    render(<SupportModal open />)
    fireEvent.click(screen.getByRole("button", { name: /Submit Ticket/i }))
    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: "Bug" } })
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: "It breaks." } })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))
    await screen.findByText("Ticket submitted")
    fireEvent.click(screen.getByRole("button", { name: /Submit another/i }))
    expect(screen.getByLabelText(/Title/i)).toBeInTheDocument()
  })

  it("renders a ticket submission error state", async () => {
    mockTicketMutation({
      mutateAsync: vi.fn().mockRejectedValue(new Error("fail")),
      isPending: false,
      isError: true,
    })
    render(<SupportModal open />)
    fireEvent.click(screen.getByRole("button", { name: /Submit Ticket/i }))
    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: "Bug" } })
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: "It breaks." } })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))
    expect(
      await screen.findByText(/Something went wrong/i)
    ).toBeInTheDocument()
  })

  it("closes when the backdrop is clicked", () => {
    const onOpenChange = vi.fn()
    render(<SupportModal open onOpenChange={onOpenChange} />)
    fireEvent.click(document.querySelector('[aria-hidden="true"]')!)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("switches back to the chat tab after opening the ticket tab", () => {
    render(<SupportModal open />)
    fireEvent.click(screen.getByRole("button", { name: /Submit Ticket/i }))
    expect(screen.getByLabelText(/Title/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Live Chat/i }))
    expect(screen.queryByLabelText(/Title/i)).not.toBeInTheDocument()
    expect(screen.getByPlaceholderText("Type your message...")).toBeInTheDocument()
  })

  it("re-adds an error bubble when the retry also fails", async () => {
    sendMessageMock
      .mockRejectedValueOnce(new Error("boom"))
      .mockRejectedValueOnce(new Error("boom again"))
    render(<SupportModal open />)
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "help" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))
    const retry = await screen.findByRole("button", { name: /Retry/i })
    fireEvent.click(retry)

    expect(
      await screen.findByText(/Something went wrong sending that/i)
    ).toBeInTheDocument()
    await waitFor(() => expect(sendMessageMock).toHaveBeenCalledTimes(2))
  })

  it("shows the typing indicator while a message is in flight", async () => {
    let resolveSend!: (v: unknown) => void
    sendMessageMock.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSend = resolve })
    )
    render(<SupportModal open />)
    fireEvent.change(screen.getByPlaceholderText("Type your message..."), {
      target: { value: "typing test" },
    })
    fireEvent.click(screen.getByRole("button", { name: /Send/i }))
    expect(document.querySelectorAll(".animate-bounce").length).toBeGreaterThan(0)

    resolveSend({ data: { conversation_id: "c-1", reply: "Done", escalated: false } })
    expect(await screen.findByText("Done")).toBeInTheDocument()
  })
})

