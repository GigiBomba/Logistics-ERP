import { useState, useCallback } from "react"
import { toast } from "sonner"
import { subscriptionApi } from "@/api/endpoints"
import { extractApiError } from "@/api/client"

interface StripeCheckoutProps {
  children: React.ReactNode
  onCheckoutStart?: () => void
  onCheckoutComplete?: (sessionId: string) => void
  onError?: (error: Error) => void
}

export function StripeCheckout({
  children,
  onCheckoutStart,
  onCheckoutComplete,
  onError,
}: StripeCheckoutProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleCheckout = useCallback(async () => {
    if (isLoading) return

    setIsLoading(true)
    onCheckoutStart?.()

    try {
      const { data } = await subscriptionApi.createCheckoutSession()
      onCheckoutComplete?.(data.session_id)
      window.location.href = data.url
    } catch (error) {
      const message = extractApiError(error)
      toast.error(message)
      onError?.(error instanceof Error ? error : new Error(message))
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, onCheckoutStart, onCheckoutComplete, onError])

  return (
    <div
      role="button"
      tabIndex={0}
      className={isLoading ? "pointer-events-none opacity-60" : "cursor-pointer"}
      onClick={handleCheckout}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          handleCheckout()
        }
      }}
      aria-busy={isLoading}
    >
      {children}
    </div>
  )
}
