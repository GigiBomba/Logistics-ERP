import { useId, useState } from "react"
import { Turnstile, type TurnstileProps } from "@marsidev/react-turnstile"
import { envConfig } from "@/config/env"
import { useLocale } from "@/i18n/locale-context"

type TurnstileTheme = "light" | "dark" | "auto"

interface TurnstileWidgetProps {
  onVerify: (token: string) => void
  onExpired?: () => void
  onError?: () => void
  theme?: TurnstileTheme
  className?: string
}

export default function TurnstileWidget({
  onVerify,
  onExpired,
  onError,
  theme,
  className,
}: TurnstileWidgetProps) {
  const id = useId()
  const { t } = useLocale()
  const [isLoading, setIsLoading] = useState(true)

  if (!envConfig.turnstileSiteKey) {
    return null
  }

  const resolvedTheme: TurnstileProps["options"] = {
    ...(theme ? { theme } : {}),
  }

  return (
    <div className={className}>
      {isLoading && (
        <p className="text-xs text-muted-foreground">{t("common.verifying")}</p>
      )}
      <Turnstile
        id={id}
        siteKey={envConfig.turnstileSiteKey}
        options={{
          ...resolvedTheme,
          size: "normal",
        }}
        onSuccess={(token) => {
          setIsLoading(false)
          onVerify(token)
        }}
        onExpire={() => {
          setIsLoading(true)
          onExpired?.()
        }}
        onError={() => {
          setIsLoading(false)
          onError?.()
        }}
        onLoad={() => {
          setIsLoading(false)
        }}
      />
    </div>
  )
}
