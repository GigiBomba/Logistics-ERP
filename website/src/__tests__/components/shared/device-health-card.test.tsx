import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { DeviceHealthCard } from "@/components/shared/device-health-card"

describe("DeviceHealthCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the device name and online badge", () => {
    render(<DeviceHealthCard deviceName="Truck 42" isOnline />)
    expect(screen.getByText("Truck 42")).toBeInTheDocument()
    expect(screen.getByText("Online")).toBeInTheDocument()
  })

  it("renders the offline badge when offline", () => {
    render(<DeviceHealthCard deviceName="Truck 42" isOnline={false} />)
    expect(screen.getByText("Offline")).toBeInTheDocument()
  })

  it("shows coordinates when lat/lng are provided and noData otherwise", () => {
    render(
      <DeviceHealthCard deviceName="A" latitude={45.1234} longitude={24.5678} />
    )
    expect(screen.getByText("45.1234, 24.5678")).toBeInTheDocument()
  })

  it("shows noData placeholder when location is missing", () => {
    render(<DeviceHealthCard deviceName="A" />)
    expect(screen.getByText("No data")).toBeInTheDocument()
  })

  it("opens Google Maps when the locate button is enabled", () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null)
    render(
      <DeviceHealthCard deviceName="A" latitude={1} longitude={2} />
    )
    fireEvent.click(screen.getByRole("button", { name: /locate on map/i }))
    expect(openSpy).toHaveBeenCalledWith(
      "https://www.google.com/maps?q=1,2",
      "_blank",
      "noopener,noreferrer"
    )
  })

  it("disables the locate button without coordinates", () => {
    render(<DeviceHealthCard deviceName="A" />)
    expect(screen.getByRole("button", { name: /locate on map/i })).toBeDisabled()
  })

  it("renders battery level with success variant for high level", () => {
    render(<DeviceHealthCard deviceName="A" batteryLevel={80} />)
    expect(screen.getByText("80%")).toBeInTheDocument()
  })

  it("renders battery level with warning variant for mid level", () => {
    render(<DeviceHealthCard deviceName="A" batteryLevel={30} />)
    expect(screen.getByText("30%")).toBeInTheDocument()
  })

  it("renders battery level with default variant for low level", () => {
    render(<DeviceHealthCard deviceName="A" batteryLevel={10} />)
    expect(screen.getByText("10%")).toBeInTheDocument()
  })

  it("hides battery row when batteryLevel is missing", () => {
    render(<DeviceHealthCard deviceName="A" />)
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument()
  })

  it("maps signal strength to labels", () => {
    const { rerender } = render(<DeviceHealthCard deviceName="A" signalStrength={90} />)
    expect(screen.getByText("Excellent")).toBeInTheDocument()
    rerender(<DeviceHealthCard deviceName="A" signalStrength={70} />)
    expect(screen.getByText("Good")).toBeInTheDocument()
    rerender(<DeviceHealthCard deviceName="A" signalStrength={50} />)
    expect(screen.getByText("Fair")).toBeInTheDocument()
    rerender(<DeviceHealthCard deviceName="A" signalStrength={30} />)
    expect(screen.getByText("Weak")).toBeInTheDocument()
    rerender(<DeviceHealthCard deviceName="A" signalStrength={5} />)
    expect(screen.getByText("Very Weak")).toBeInTheDocument()
  })

  it("renders speed with one decimal", () => {
    render(<DeviceHealthCard deviceName="A" speed={72.456} />)
    expect(screen.getByText("72.5 km/h")).toBeInTheDocument()
  })

  describe("formatRelativeTime", () => {
    it("shows 'Just now' for under a minute", () => {
      render(<DeviceHealthCard deviceName="A" lastSeen={new Date(Date.now() - 10_000).toISOString()} />)
      expect(screen.getByText("Just now")).toBeInTheDocument()
    })

    it("shows minutes ago", () => {
      render(<DeviceHealthCard deviceName="A" lastSeen={new Date(Date.now() - 5 * 60_000).toISOString()} />)
      expect(screen.getByText("5m ago")).toBeInTheDocument()
    })

    it("shows hours ago", () => {
      render(<DeviceHealthCard deviceName="A" lastSeen={new Date(Date.now() - 3 * 3_600_000).toISOString()} />)
      expect(screen.getByText("3h ago")).toBeInTheDocument()
    })

    it("shows days ago within a week", () => {
      render(<DeviceHealthCard deviceName="A" lastSeen={new Date(Date.now() - 2 * 86_400_000).toISOString()} />)
      expect(screen.getByText("2d ago")).toBeInTheDocument()
    })

    it("shows the date for older timestamps", () => {
      const old = new Date(Date.now() - 20 * 86_400_000).toISOString()
      render(<DeviceHealthCard deviceName="A" lastSeen={old} />)
      expect(screen.getByText(new Date(old).toLocaleDateString())).toBeInTheDocument()
    })
  })
})
