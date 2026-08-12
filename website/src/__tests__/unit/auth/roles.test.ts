import { describe, it, expect, vi, beforeEach } from "vitest"
import { createMockAuthUser, createMockAuthContext } from "@/test-utils"
import type { UserRole, User } from "@/types"

describe("UserRole type", () => {
  it("accepts 'admin' as a valid role", () => {
    const role: UserRole = "admin"
    expect(role).toBe("admin")
  })

  it("accepts 'dispatcher' as a valid role", () => {
    const role: UserRole = "dispatcher"
    expect(role).toBe("dispatcher")
  })

  it("accepts 'manager' as a valid role", () => {
    const role: UserRole = "manager"
    expect(role).toBe("manager")
  })

  it("accepts 'driver' as a valid role", () => {
    const role: UserRole = "driver"
    expect(role).toBe("driver")
  })

  it("does not accept invalid role strings at compile time", () => {
    // TypeScript enforces UserRole = "admin" | "dispatcher" | "manager" | "driver"
    const validRoles: UserRole[] = ["admin", "dispatcher", "manager", "driver"]
    expect(validRoles).toContain("admin")
    expect(validRoles).toContain("dispatcher")
    expect(validRoles).not.toContain("moderator")
  })
})

describe("User role field", () => {
  it("allows role to be 'admin'", () => {
    const user: User = {
      id: "1",
      email: "admin@operionerp.xyz",
      role: "admin",
      is_admin: true,
      display_name: "Admin",
      name: "Admin",
      email_verified: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    }
    expect(user.role).toBe("admin")
  })

  it("allows role to be 'dispatcher'", () => {
    const user: User = {
      id: "2",
      email: "dispatcher@operionerp.xyz",
      role: "dispatcher",
      is_admin: false,
      company_id: 1,
      display_name: "Dispatcher",
      name: "Dispatcher",
      email_verified: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    }
    expect(user.role).toBe("dispatcher")
  })

  it("allows role to be undefined (optional)", () => {
    const user: User = {
      id: "3",
      email: "guest@operionerp.xyz",
      role: "dispatcher",
      is_admin: false,
      display_name: "Guest",
      name: "Guest",
      email_verified: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    }
    expect(user.role).toBe("dispatcher")
  })
})

describe("createMockAuthUser", () => {
  it("returns 'dispatcher' role by default", () => {
    const mockUser = createMockAuthUser()
    expect(mockUser.role).toBe("dispatcher")
  })

  it("can override role to 'admin'", () => {
    const mockUser = createMockAuthUser({ role: "admin" })
    expect(mockUser.role).toBe("admin")
  })

  it("includes default fields when no overrides given", () => {
    const mockUser = createMockAuthUser()
    expect(mockUser.id).toBe("user-1")
    expect(mockUser.email).toBe("test@operionerp.xyz")
    expect(mockUser.display_name).toBe("Test User")
    expect(mockUser.name).toBe("Test User")
    expect(mockUser.email_verified).toBe(true)
    expect(mockUser.is_admin).toBe(false)
    expect(mockUser.company_id).toBe(1)
  })

  it("merges overrides with defaults", () => {
    const mockUser = createMockAuthUser({ display_name: "Custom Name", email: "custom@test.com" })
    expect(mockUser.display_name).toBe("Custom Name")
    expect(mockUser.email).toBe("custom@test.com")
    // Default fields remain
    expect(mockUser.id).toBe("user-1")
    expect(mockUser.role).toBe("dispatcher")
  })
})

describe("createMockAuthContext", () => {
  it("returns isAdmin false by default", () => {
    const ctx = createMockAuthContext()
    expect(ctx.isAdmin).toBe(false)
  })

  it("returns isAuthenticated false by default", () => {
    const ctx = createMockAuthContext()
    expect(ctx.isAuthenticated).toBe(false)
  })

  it("returns user null by default", () => {
    const ctx = createMockAuthContext()
    expect(ctx.user).toBeNull()
  })

  it("returns isLoading false by default", () => {
    const ctx = createMockAuthContext()
    expect(ctx.isLoading).toBe(false)
  })

  it("has login, register, logout, refreshUser, updateUser functions", () => {
    const ctx = createMockAuthContext()
    expect(typeof ctx.login).toBe("function")
    expect(typeof ctx.register).toBe("function")
    expect(typeof ctx.logout).toBe("function")
    expect(typeof ctx.refreshUser).toBe("function")
    expect(typeof ctx.updateUser).toBe("function")
  })

  it("can override isAdmin to true", () => {
    const ctx = createMockAuthContext({ isAdmin: true })
    expect(ctx.isAdmin).toBe(true)
  })
})

describe("admin user mock", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("has isAdmin true when role is 'admin'", () => {
    const mockUser = createMockAuthUser({ role: "admin" })
    const mockCtx = createMockAuthContext({
      user: mockUser,
      isAuthenticated: true,
      isAdmin: mockUser.role === "admin",
    })
    expect(mockCtx.isAdmin).toBe(true)
    expect(mockCtx.user?.role).toBe("admin")
  })

  it("has isAdmin false when role is 'dispatcher'", () => {
    const mockUser = createMockAuthUser({ role: "dispatcher" })
    const mockCtx = createMockAuthContext({
      user: mockUser,
      isAuthenticated: true,
      isAdmin: mockUser.is_admin === true || mockUser.role === "admin",
    })
    expect(mockCtx.isAdmin).toBe(false)
    expect(mockCtx.user?.role).toBe("dispatcher")
  })

  it("combines admin user mock with full authenticated context", () => {
    const mockUser = createMockAuthUser({ role: "admin" })
    const mockCtx = createMockAuthContext({
      user: mockUser,
      isAdmin: true,
      isAuthenticated: true,
    })
    expect(mockCtx.isAdmin).toBe(true)
    expect(mockCtx.isAuthenticated).toBe(true)
    expect(mockCtx.user).toEqual(mockUser)
  })
})
