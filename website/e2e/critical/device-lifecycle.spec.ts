import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration, waitForHydration } from "../helpers"

/**
 * Device Lifecycle Tests
 *
 * Tests: list devices → deactivate → verify removed from active list.
 *
 * Uses mocked API data to be self-contained.
 *
 * NOTE: the real devices API lives under /api/v1/mobile/devices and the
 * sessions API under /api/v1/auth/sessions — the mocks must use those paths.
 */

const MOCK_DEVICES = [
  {
    id: 1,
    device_id: "DEV-001",
    device_name: "Driver Phone - Samsung Galaxy S24",
    platform: "Android 14",
    user_email: "driver@operionerp.xyz",
    user_name: "John Driver",
    is_active: true,
    last_seen: new Date().toISOString(),
    created_at: "2026-03-15T10:00:00Z",
  },
  {
    id: 2,
    device_id: "DEV-002",
    device_name: "Tablet - iPad Pro",
    platform: "iOS 18",
    user_email: "dispatcher@operionerp.xyz",
    user_name: "Jane Dispatch",
    is_active: true,
    last_seen: new Date().toISOString(),
    created_at: "2026-04-01T08:30:00Z",
  },
  {
    id: 3,
    device_id: "DEV-003",
    device_name: "Old Phone - OnePlus 9",
    platform: "Android 13",
    user_email: "former@operionerp.xyz",
    user_name: "Former Driver",
    is_active: false,
    last_seen: "2026-05-01T12:00:00Z",
    created_at: "2026-02-10T09:00:00Z",
  },
]

const ACTIVE_DEVICES = MOCK_DEVICES.filter((d) => d.is_active)

test.describe("Device Lifecycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Authenticate as admin via the cookie-only refresh bootstrap.
    await mockAuthAs(page, createUser("admin", { id: "1", email: "admin@operionerp.xyz", name: "Admin User" }))

    // Mock the devices API (real path: /api/v1/mobile/devices)
    await page.route("**/api/v1/mobile/devices**", async (route) => {
      if (route.request().method() === "DELETE") {
        // Handle deactivation: respond with success
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) })
      } else {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_DEVICES) })
      }
    })
    // Mock sessions API (real path: /api/v1/auth/sessions — used on the same page)
    await page.route("**/api/v1/auth/sessions**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ sessions: [] }) })
    })
  })

  test("lists all devices with active/inactive counts", async ({ page }) => {
    await page.goto("/dashboard/devices")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/dashboard\/devices/, { timeout: 15000 })

    // Check stat cards (exact — "Active Devices" is a substring of "Inactive Devices")
    await expect(page.getByText("Total Devices", { exact: true })).toBeVisible()
    await expect(page.getByText("Active Devices", { exact: true })).toBeVisible()
    await expect(page.getByText("Inactive Devices", { exact: true })).toBeVisible()

    // Check devices are rendered
    for (const device of MOCK_DEVICES) {
      await expect(page.getByText(device.device_name)).toBeVisible()
    }
  })

  test("deactivates a device and it moves to inactive tab", async ({ page }) => {
    await page.goto("/dashboard/devices")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/dashboard\/devices/, { timeout: 15000 })

    // Click the first "Deactivate" button — this opens the two-step confirm
    const deactivateButton = page.getByRole("button", { name: /deactivate/i }).first()
    await expect(deactivateButton).toBeVisible()
    await deactivateButton.click()

    // Confirm: "Are you sure?" + a destructive "Deactivate" button appears
    const confirmButton = page.getByRole("button", { name: /^deactivate$/i }).first()
    await expect(confirmButton).toBeVisible()
    await confirmButton.click()

    // After deactivation, the devices list should refetch. We simulate that by
    // returning updated mock data with the device deactivated.
    await page.route("**/api/v1/mobile/devices**", async (route) => {
      if (route.request().method() === "GET") {
        const updatedDevices = MOCK_DEVICES.map((d) =>
          d.device_id === "DEV-001" ? { ...d, is_active: false } : d
        )
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(updatedDevices) })
      }
    })

    // Reload the page to pick up the new mock route
    await page.reload()

    // The deactivated device should no longer appear in the "Active" tab.
    // The tab's accessible name includes the count badge (e.g. "Active 3"),
    // so use a prefix match, not exact ("Active" is a substring of "Inactive"
    // but ^Active does not match "Inactive").
    await page.getByRole("tab", { name: /^Active/ }).click()
    await expect(page.getByText("Driver Phone - Samsung Galaxy S24")).not.toBeVisible()
  })

  test("shows empty state when no devices exist", async ({ page }) => {
    await page.route("**/api/v1/mobile/devices**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
      }
    })
    await page.goto("/dashboard/devices")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/dashboard\/devices/, { timeout: 15000 })
    await expect(page.getByText(/no devices registered/i)).toBeVisible()
  })
})
