import { useEffect } from "react"
import { useAppNavigate } from "@/hooks/useAppNavigate"

export function AppNavigate({ to, replace = false }: { to: string; replace?: boolean }) {
  const navigate = useAppNavigate()
  useEffect(() => { navigate(to, { replace }) }, [to, replace, navigate])
  return null
}
