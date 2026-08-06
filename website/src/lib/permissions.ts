import type { UserRole } from "@/types"

export type Permission =
  | "billing.view"
  | "billing.manage"
  | "team.invite"
  | "team.remove"
  | "team.change_role"
  | "devices.manage"
  | "licenses.manage"
  | "support.tickets"
  | "audit.view"
  | "settings.manage"
  | "ops.access"

const PERMISSION_MATRIX: Record<UserRole, Permission[]> = {
  owner: [
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
  ],
  admin: [
    "billing.view",
    "team.invite",
    "team.remove",
    "team.change_role",
    "devices.manage",
    "licenses.manage",
    "support.tickets",
    "audit.view",
    "settings.manage",
  ],
  manager: [
    "devices.manage",
    "licenses.manage",
    "support.tickets",
  ],
  dispatcher: [
    "support.tickets",
  ],
  driver: [
    "support.tickets",
  ],
}

export function hasPermission(userRole: UserRole, permission: Permission): boolean {
  return PERMISSION_MATRIX[userRole]?.includes(permission) ?? false
}

export function getAllPermissions(role: UserRole): Permission[] {
  return PERMISSION_MATRIX[role] ?? []
}

export { PERMISSION_MATRIX }
