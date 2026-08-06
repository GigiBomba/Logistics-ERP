import { http, HttpResponse } from "msw"
import type { DeviceInfo } from "@/types"

const mockDevices: DeviceInfo[] = [
  {
    id: 1,
    device_id: "DEV-001",
    device_name: "Scanner Alpha",
    platform: "windows",
    user_email: "driver1@operion.dev",
    user_name: "John Driver",
    is_active: true,
    last_seen: "2026-07-29T10:00:00Z",
    created_at: "2026-01-15T08:00:00Z",
  },
  {
    id: 2,
    device_id: "DEV-002",
    device_name: "Scanner Beta",
    platform: "android",
    user_email: "driver2@operion.dev",
    user_name: "Jane Driver",
    is_active: true,
    last_seen: "2026-07-28T16:30:00Z",
    created_at: "2026-02-20T09:00:00Z",
  },
  {
    id: 3,
    device_id: "DEV-003",
    device_name: "Warehouse Scanner 1",
    platform: "windows",
    user_email: "warehouse@operion.dev",
    user_name: "Bob Warehouse",
    is_active: false,
    last_seen: "2026-06-15T12:00:00Z",
    created_at: "2026-03-10T10:00:00Z",
  },
]

export const devicesHandlers = [
  http.get("*/api/v1/devices", () => {
    return HttpResponse.json({
      items: mockDevices,
      total: mockDevices.length,
      page: 1,
      page_size: 20,
    })
  }),

  http.get("*/api/v1/devices/:id", ({ params }) => {
    const device = mockDevices.find((d) => d.id === Number(params.id))
    if (!device) {
      return HttpResponse.json({ detail: "Device not found" }, { status: 404 })
    }
    return HttpResponse.json(device)
  }),

  http.delete("*/api/v1/devices/:id", ({ params }) => {
    const device = mockDevices.find((d) => d.id === Number(params.id))
    if (!device) {
      return HttpResponse.json({ detail: "Device not found" }, { status: 404 })
    }
    return HttpResponse.json({ detail: "Device deleted successfully" })
  }),
]
