import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@/test-utils"
import DevicesPage from "@/pages/dashboard/devices"
import {
  useDevices,
  useDeactivateDevices,
  useRequestPairingToken,
  usePairingStatus,
} from "@/services/queries"
import { toDataURL } from "qrcode"
import type { DeviceInfo } from "@/types"

vi.mock("@/services/queries", () => ({
  useDevices: vi.fn(),
  useDeactivateDevice: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useDeactivateDevices: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useRequestPairingToken: vi.fn(() => ({
    data: null,
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: false,
    isError: false,
  })),
  usePairingStatus: vi.fn(() => ({
    data: { valid: false },
    isLoading: false,
    isError: false,
  })),
  useSessions: vi.fn(() => ({ data: [], isLoading: false, isError: false })),
  useRevokeSession: vi.fn(() => ({ mutate: vi.fn() })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

vi.mock("qrcode", () => ({
  toDataURL: vi.fn(),
}))

const mockToDataURL = toDataURL as unknown as ReturnType<typeof vi.fn>

// useMutation resolves to an AxiosResponse, so the mock data is nested under `.data`.
const MOCK_PAIRING_RESPONSE = {
  data: {
    pairing_token: "pair-tok-1",
    expires_at: "2026-09-13T00:00:00Z",
    qr_data: "operion://pair?token=pair-tok-1",
  },
}

function makeDevice(overrides: Partial<DeviceInfo> = {}): DeviceInfo {
  return {
    id: 1,
    device_id: "dev-1",
    device_name: "Driver Phone",
    platform: "Android",
    user_email: "driver@operion.dev",
    user_name: "Ion Popescu",
    is_active: true,
    last_seen: new Date().toISOString(),
    created_at: "2026-01-10T00:00:00Z",
    ...overrides,
  }
}

function mockDevices(devices: DeviceInfo[]) {
  vi.mocked(useDevices).mockReturnValue({
    data: devices,
    isLoading: false,
    isError: false,
  } as any)
}

function mockPairingSuccess(valid: boolean) {
  vi.mocked(usePairingStatus).mockReturnValue({
    data: { valid, user_id: "user-1", company_id: "co-1", expires_in: 300 },
    isLoading: false,
    isError: false,
  } as any)
}

describe("DevicesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockToDataURL.mockResolvedValue("data:image/png;base64,QR")
    mockDevices([makeDevice(), makeDevice({ id: 2, device_id: "dev-2", device_name: "Tablet" })])
    vi.mocked(useRequestPairingToken).mockReturnValue({
      data: null,
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
    } as any)
    mockPairingSuccess(false)
  })

  afterEach(() => {
    localStorage.removeItem("operion-locale")
    vi.useRealTimers()
  })

  it("renders registered devices", () => {
    render(<DevicesPage />)
    expect(screen.getByText("Driver Phone")).toBeInTheDocument()
    expect(screen.getByText("Tablet")).toBeInTheDocument()
    expect(screen.queryByText("2 selected")).not.toBeInTheDocument()
  })

  it("shows the bulk action bar and deactivates the selected devices", () => {
    const bulkMutate = vi.fn()
    vi.mocked(useDeactivateDevices).mockReturnValue({ mutate: bulkMutate, isPending: false } as any)
    render(<DevicesPage />)

    fireEvent.click(screen.getByLabelText("Select device: Driver Phone"))
    expect(screen.getByText("1 selected")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /bulk deactivate/i }))
    expect(bulkMutate).toHaveBeenCalledWith(["dev-1"])

    // Selection is cleared after the bulk action.
    expect(screen.queryByText("1 selected")).not.toBeInTheDocument()
  })

  it("select-all marks every device and Clear resets the selection", () => {
    const bulkMutate = vi.fn()
    vi.mocked(useDeactivateDevices).mockReturnValue({ mutate: bulkMutate, isPending: false } as any)
    render(<DevicesPage />)

    fireEvent.click(screen.getByLabelText("Select device: Driver Phone"))
    fireEvent.click(screen.getByLabelText("Select device: Tablet"))
    expect(screen.getByText("2 selected")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /clear selection/i }))
    expect(screen.queryByText("2 selected")).not.toBeInTheDocument()
  })

  it("opens the pairing modal and shows the QR image after the token fetch", async () => {
    vi.mocked(useRequestPairingToken).mockReturnValue({
      data: MOCK_PAIRING_RESPONSE,
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
    } as any)
    render(<DevicesPage />)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /pair device/i }))

    const dialog = screen.getByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(screen.getByText("Pair a new device")).toBeInTheDocument()
    expect(mockToDataURL).toHaveBeenCalledWith("operion://pair?token=pair-tok-1")

    const img = await screen.findByRole("img", { name: /scan the qr code/i })
    expect(img).toHaveAttribute("src", "data:image/png;base64,QR")
  })

  it("shows the success state and closes the modal once pairing validates", () => {
    vi.useFakeTimers()
    vi.mocked(useRequestPairingToken).mockReturnValue({
      data: MOCK_PAIRING_RESPONSE,
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
    } as any)
    mockPairingSuccess(true)
    render(<DevicesPage />)

    fireEvent.click(screen.getByRole("button", { name: /pair device/i }))
    expect(screen.getByText("Device paired successfully")).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1300)
    })

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})