import { RequireRole } from "./require-role"
import { Outlet } from "react-router"

export function AdminLayout() {
  return (
    <RequireRole roles={["owner", "admin"]}>
      <Outlet />
    </RequireRole>
  )
}
