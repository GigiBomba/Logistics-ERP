import { useState, useCallback } from "react"
import { toast } from "sonner"
import { subscriptionApi } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { cn } from "@/lib/utils"

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
    <button
      type="button"
      onClick={handleCheckout}
      disabled={isLoading}
      aria-busy={isLoading}
      className={cn(
        "w-full cursor-pointer appearance-none border-0 bg-transparent p-0 text-left",
        isLoading && "pointer-events-none opacity-60"
      )}
    >
      {children}
    </button>
  )
}
