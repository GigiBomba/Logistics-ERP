import { describe, it, expect } from "vitest"
import {
  hasPermission,
  getAllPermissions,
  PERMISSION_MATRIX,
  type Permission,
} from "@/lib/permissions"
import type { UserRole } from "@/types"

// Every permission in the union must be granted to the owner role — this is a
// contract invariant that guards against a new permission being added without
// being wired into the matrix.
const ALL_PERMISSIONS: Permission[] = [
  "billing.view",
  "billing.manage",
  "team.invite",
  "team.remove",
  "team.change_role",
  "devices.manage",
  "licenses.manage",
  "support.tickets",
  "audit.view",
  "settings.manage",
  "ops.access",
]

const ROLES: UserRole[] = ["owner", "admin", "manager", "dispatcher", "driver"]

describe("PERMISSION_MATRIX", () => {
  it("defines an entry for every role", () => {
    for (const role of ROLES) {
      expect(Array.isArray(PERMISSION_MATRIX[role])).toBe(true)
    }
  })

  it("gives the owner every permission in the system", () => {
    for (const permission of ALL_PERMISSIONS) {
      expect(PERMISSION_MATRIX.owner).toContain(permission)
    }
  })

  it("owner has no extra permissions outside the union", () => {
    expect(PERMISSION_MATRIX.owner.length).toBe(ALL_PERMISSIONS.length)
  })

  it("admin includes all admin-level permissions but excludes owner-only ones", () => {
    const admin = PERMISSION_MATRIX.admin
    expect(admin).toContain("billing.view")
    expect(admin).toContain("team.invite")
    expect(admin).toContain("team.remove")
    expect(admin).toContain("team.change_role")
    expect(admin).toContain("devices.manage")
    expect(admin).toContain("licenses.manage")
    expect(admin).toContain("support.tickets")
    expect(admin).toContain("audit.view")
    expect(admin).toContain("settings.manage")
    expect(admin).not.toContain("billing.manage")
    expect(admin).not.toContain("ops.access")
  })

  it("manager gets operational permissions only", () => {
    const manager = PERMISSION_MATRIX.manager
    expect(manager).toEqual(["devices.manage", "licenses.manage", "support.tickets"])
  })

  it("dispatcher and driver only get support.tickets", () => {
    expect(PERMISSION_MATRIX.dispatcher).toEqual(["support.tickets"])
    expect(PERMISSION_MATRIX.driver).toEqual(["support.tickets"])
  })
})

describe("getAllPermissions()", () => {
  it("returns the full list for each role", () => {
    expect(getAllPermissions("owner")).toHaveLength(ALL_PERMISSIONS.length)
    expect(getAllPermissions("admin")).toEqual(PERMISSION_MATRIX.admin)
    expect(getAllPermissions("manager")).toEqual(PERMISSION_MATRIX.manager)
    expect(getAllPermissions("dispatcher")).toEqual(["support.tickets"])
    expect(getAllPermissions("driver")).toEqual(["support.tickets"])
  })

  it("returns an empty array for an unknown role", () => {
    expect(getAllPermissions("superuser" as UserRole)).toEqual([])
  })

  it("returns the same reference as the matrix entry (callers must not mutate it)", () => {
    // Documented behavior: getAllPermissions does NOT copy — it returns the
    // matrix entry directly, so tests (and callers) must treat it as read-only.
    expect(getAllPermissions("admin")).toBe(PERMISSION_MATRIX.admin)
  })
})

describe("hasPermission()", () => {
  it("returns true for permissions granted to the role", () => {
    expect(hasPermission("owner", "billing.manage")).toBe(true)
    expect(hasPermission("admin", "settings.manage")).toBe(true)
    expect(hasPermission("manager", "licenses.manage")).toBe(true)
    expect(hasPermission("dispatcher", "support.tickets")).toBe(true)
    expect(hasPermission("driver", "support.tickets")).toBe(true)
  })

  it("returns false for permissions not granted to the role", () => {
    expect(hasPermission("admin", "billing.manage")).toBe(false)
    expect(hasPermission("manager", "billing.view")).toBe(false)
    expect(hasPermission("dispatcher", "devices.manage")).toBe(false)
    expect(hasPermission("driver", "audit.view")).toBe(false)
  })

  it("returns false for an unknown role", () => {
    expect(hasPermission("superuser" as UserRole, "billing.view")).toBe(false)
  })

  it("returns false for an unknown permission", () => {
    expect(hasPermission("owner", "nuclear.launch" as Permission)).toBe(false)
  })
})
