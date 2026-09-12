import { describe, it, expect, vi, beforeEach } from "vitest"

const { accessTokenMock, createTicketMock, trackErrorMock } = vi.hoisted(() => ({
  accessTokenMock: vi.fn<() => string | null>(() => null),
  createTicketMock: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
  trackErrorMock: vi.fn(),
}))

vi.mock("@/api/client", () => ({
  getAccessToken: accessTokenMock,
  default: {},
}))

vi.mock("@/api/endpoints", () => ({
  supportApi: { createTicket: createTicketMock },
}))

vi.mock("@/services/analytics", () => ({
  trackError: trackErrorMock,
}))

import { reportFatalError } from "@/services/error-reporting"

const boom = new Error("boom")

describe("reportFatalError", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    accessTokenMock.mockReturnValue(null)
  })

  it("files a support ticket when authenticated", () => {
    accessTokenMock.mockReturnValue("token-123")
    reportFatalError(boom, "    at App")

    expect(createTicketMock).toHaveBeenCalledTimes(1)
    expect(createTicketMock).toHaveBeenCalledWith(
      expect.objectContaining({
        category: "bug",
        subject: "[Fatal UI Error]",
        description: expect.stringContaining("boom"),
      })
    )
    expect(trackErrorMock).toHaveBeenCalledTimes(1)
  })

  it("does not file a ticket when unauthenticated", () => {
    reportFatalError(boom, "    at App")

    expect(createTicketMock).not.toHaveBeenCalled()
    expect(trackErrorMock).toHaveBeenCalledTimes(1)
  })

  it("suppresses duplicate signatures within the same session", () => {
    accessTokenMock.mockReturnValue("token-123")
    reportFatalError(boom, "    at App")
    reportFatalError(boom, "    at App")

    expect(createTicketMock).toHaveBeenCalledTimes(1)
    // tracking still fires on every call
    expect(trackErrorMock).toHaveBeenCalledTimes(2)
  })

  it("treats a different error as a distinct signature", () => {
    accessTokenMock.mockReturnValue("token-123")
    reportFatalError(new Error("one"), "    at App")
    reportFatalError(new Error("two"), "    at App")

    expect(createTicketMock).toHaveBeenCalledTimes(2)
  })

  it("always tracks the error even when no ticket is filed", () => {
    reportFatalError(boom, "    at App")
    reportFatalError(new Error("late"), "    at App")

    expect(createTicketMock).not.toHaveBeenCalled()
    expect(trackErrorMock).toHaveBeenCalledTimes(2)
  })

  it("swallows createTicket failures so they never mask the crash", () => {
    accessTokenMock.mockReturnValue("token-123")
    createTicketMock.mockRejectedValueOnce(new Error("network down"))

    expect(() => reportFatalError(boom, "    at App")).not.toThrow()
    expect(createTicketMock).toHaveBeenCalledTimes(1)
    expect(trackErrorMock).toHaveBeenCalledTimes(1)
  })
})