import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { DeviceList } from "@/components/shared/device-list"
import type { DeviceInfo } from "@/types"

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

describe("DeviceList", () => {
  it("renders the card variant with device details", () => {
    render(<DeviceList devices={[makeDevice()]} variant="card" />)

    expect(screen.getByText("Driver Phone")).toBeInTheDocument()
    expect(screen.getByText("Android")).toBeInTheDocument()
    expect(screen.getByText("Ion Popescu")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("renders an empty state message when there are no devices", () => {
    render(<DeviceList devices={[]} emptyMessage="No devices yet" />)
    expect(screen.getByText("No devices yet")).toBeInTheDocument()
  })

  it("shows a loading indicator when isLoading is true", () => {
    render(<DeviceList devices={[]} isLoading />)
    expect(document.querySelector(".animate-spin")).not.toBeNull()
  })

  it("renders the table variant with device rows", () => {
    render(
      <DeviceList
        devices={[makeDevice(), makeDevice({ id: 2, device_id: "dev-2", device_name: "Tablet", platform: "iPadOS", is_active: false })]}
        variant="table"
      />
    )

    expect(screen.getByText("Driver Phone")).toBeInTheDocument()
    expect(screen.getByText("Tablet")).toBeInTheDocument()
    // Status badges for both rows
    expect(screen.getByText("Active")).toBeInTheDocument()
    expect(screen.getByText("Inactive")).toBeInTheDocument()
  })

  it("calls onDeactivate with the device_id when the card deactivate action is clicked", () => {
    const onDeactivate = vi.fn()
    render(<DeviceList devices={[makeDevice()]} variant="card" onDeactivate={onDeactivate} />)

    fireEvent.click(screen.getByRole("button", { name: /deactivate/i }))
    expect(onDeactivate).toHaveBeenCalledWith("dev-1")
  })

  it("does not show the default deactivate action for inactive devices", () => {
    render(<DeviceList devices={[makeDevice({ is_active: false })]} variant="card" onDeactivate={vi.fn()} />)
    expect(screen.queryByRole("button", { name: /deactivate/i })).not.toBeInTheDocument()
  })

  it("calls onDeactivate when the table row deactivate action is clicked", () => {
    const onDeactivate = vi.fn()
    render(<DeviceList devices={[makeDevice()]} variant="table" onDeactivate={onDeactivate} />)

    fireEvent.click(screen.getByRole("button", { name: /deactivate/i }))
    expect(onDeactivate).toHaveBeenCalledWith("dev-1")
  })

  it("renders custom actions via the renderActions slot", () => {
    render(
      <DeviceList
        devices={[makeDevice()]}
        variant="card"
        renderActions={() => <button type="button">Custom Action</button>}
      />
    )
    expect(screen.getByRole("button", { name: /custom action/i })).toBeInTheDocument()
  })
})
