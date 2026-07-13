"use client"

import { useState, useCallback } from "react"
import { motion } from "motion/react"
import { CheckCircle2, Loader2, Mail } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useLocale } from "@/i18n/locale-context"
// TODO: Implement when backend endpoint is ready
// import { newsletterApi } from "@/api/endpoints"
// import { extractApiError } from "@/api/client"
import { toast } from "sonner"

interface NewsletterFormProps {
  variant?: "inline" | "card" | "footer"
  className?: string
}

const PREFERENCE_OPTIONS = [
  { id: "product_updates", label: "Product Updates", defaultChecked: true },
  { id: "blog_digest", label: "Blog Digest", defaultChecked: false },
  { id: "event_invites", label: "Event Invites", defaultChecked: false },
] as const

export function NewsletterForm({ variant = "card", className }: NewsletterFormProps) {
  const { t } = useLocale()
  const [email, setEmail] = useState("")
  const [preferences, setPreferences] = useState<string[]>(
    PREFERENCE_OPTIONS.filter((o) => o.defaultChecked).map((o) => o.id)
  )
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [errorMessage, setErrorMessage] = useState("")

  const togglePreference = useCallback((id: string) => {
    setPreferences((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }, [])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!email.trim()) return

      setStatus("loading")
      setErrorMessage("")

      try {
        // TODO: Implement when backend endpoint is ready
        // await newsletterApi.subscribe({ email: email.trim(), preferences })
        toast.success(t("newsletter.success"))
        setStatus("success")
        setEmail("")
      } catch {
        setStatus("error")
        setErrorMessage(t("newsletter.error"))
      }
    },
    [email, preferences]
  )

  // ── Success State ──────────────────────────────────────────
  if (status === "success") {
    const motionProps = {
      initial: { opacity: 0, y: 8 },
      animate: { opacity: 1, y: 0 },
      transition: { duration: 0.3, ease: "easeOut" as const },
    }

    if (variant === "card") {
      return (
        <Card className={cn("text-center", className)}>
          <CardContent className="pt-6">
            <motion.div {...motionProps}>
              <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
              <h3 className="mt-4 text-lg font-semibold">{t("newsletter.success")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {t("newsletter.checkEmail")}
              </p>
            </motion.div>
          </CardContent>
        </Card>
      )
    }

    return (
      <motion.div {...motionProps} className={cn("flex items-center gap-3", className)}>
        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
        <p className="text-sm text-muted-foreground">
          {t("newsletter.success")} {t("newsletter.checkEmail")}
        </p>
      </motion.div>
    )
  }

  // ── Inline Variant ─────────────────────────────────────────
  if (variant === "inline") {
    return (
      <form
        onSubmit={handleSubmit}
        className={cn("flex flex-col gap-3 sm:flex-row sm:items-end", className)}
      >
        <div className="flex-1">
          <Input
            type="email"
            placeholder={t("newsletter.placeholder")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={status === "loading"}
            required
            aria-label={t("newsletter.placeholder")}
          />
        </div>
        <Button type="submit" disabled={status === "loading" || !email.trim()}>
          {status === "loading" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("newsletter.subscribing")}
            </>
          ) : (
            t("newsletter.subscribe")
          )}
        </Button>
        {status === "error" && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-xs text-destructive sm:col-span-2"
          >
            {errorMessage}
          </motion.p>
        )}
      </form>
    )
  }

  // ── Footer Variant ─────────────────────────────────────────
  if (variant === "footer") {
    return (
      <form onSubmit={handleSubmit} className={cn("space-y-3", className)}>
        <p className="text-sm text-muted-foreground">
          {t("newsletter.desc")}
        </p>
        <div className="flex gap-2">
          <Input
            type="email"
            placeholder={t("newsletter.placeholder")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={status === "loading"}
            required
            aria-label={t("newsletter.placeholder")}
            className="h-9 text-sm"
          />
          <Button type="submit" size="sm" disabled={status === "loading" || !email.trim()}>
            {status === "loading" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              t("newsletter.subscribe")
            )}
          </Button>
        </div>
        {status === "error" && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-xs text-destructive"
          >
            {errorMessage}
          </motion.p>
        )}
      </form>
    )
  }

  // ── Card Variant (default) ─────────────────────────────────
  return (
    <Card className={cn("overflow-hidden", className)}>
      <form onSubmit={handleSubmit}>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-primary" />
            <CardTitle>{t("newsletter.title")}</CardTitle>
          </div>
          <CardDescription>
            {t("newsletter.desc")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Input
              type="email"
              placeholder={t("newsletter.placeholder")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={status === "loading"}
              required
              aria-label={t("newsletter.placeholder")}
            />
          </div>
          <fieldset>
            <legend className="text-sm font-medium mb-2">{t("newsletter.preferences")}</legend>
            <div className="space-y-2">
              {PREFERENCE_OPTIONS.map((opt) => (
                <label
                  key={opt.id}
                  className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={preferences.includes(opt.id)}
                    onChange={() => togglePreference(opt.id)}
                    disabled={status === "loading"}
                    className="h-4 w-4 rounded border-input text-primary focus:ring-primary"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>
          {status === "error" && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-sm text-destructive"
            >
              {errorMessage}
            </motion.p>
          )}
        </CardContent>
        <CardFooter>
          <Button
            type="submit"
            className="w-full"
            disabled={status === "loading" || !email.trim()}
          >
            {status === "loading" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("newsletter.subscribing")}
              </>
            ) : (
              t("newsletter.subscribe")
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
