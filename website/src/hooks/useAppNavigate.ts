import { useCallback } from "react"
import { navigate as vikeNavigate } from "vike/client/router"

export function useAppNavigate() {
  return useCallback((to: string, options?: { replace?: boolean }) => {
    vikeNavigate(to, { overwriteLastHistoryEntry: options?.replace ?? false })
  }, [])
}
