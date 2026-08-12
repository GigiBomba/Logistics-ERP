import { useState } from "react"
import { motion } from "motion/react"
import { SeoHead } from "@/components/seo/seo-head"
import { Mail, CheckCircle2, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { siteConfig } from "@/config/site"
import { useLocale } from "@/i18n/locale-context"
import { useSubscribeNewsletter } from "@/services/queries"

export default function NewsletterPage() {
  const { t } = useLocale()
  const [email, setEmail] = useState("")
  const [subscribed, setSubscribed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mutation = useSubscribeNewsletter()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email) return
    setError(null)
    mutation.mutate(
      { email },
      {
        onSuccess: () => setSubscribed(true),
        onError: () => setError(t("newsletter.error")),
      }
    )
  }

  return (
    <div className="container-wide py-16 md:py-24">
      <SeoHead title="Newsletter — Operion" description="Subscribe to the Operion newsletter for logistics industry insights, product updates, and transport management tips." canonical="https://operionerp.xyz/newsletter" />
      <div className="mx-auto max-w-2xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
            <Mail className="h-8 w-8 text-primary" />
          </div>

          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            {t("newsletter.title")}
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Get the latest news, product updates, and insights from {siteConfig.name}
            delivered to your inbox.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="mt-10"
        >
          {subscribed ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-xl border bg-card p-8 text-center"
            >
              <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
              <h2 className="mt-4 text-xl font-semibold">{t("newsletter.success")}</h2>
              <p className="mt-2 text-muted-foreground">
                {t("newsletter.checkEmail")}
              </p>
            </motion.div>
          ) : (
            <>
              {error && (
                <div className="mx-auto mb-4 flex max-w-md items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              <form onSubmit={handleSubmit} className="mx-auto flex max-w-md gap-3">
                <Input
                  type="email"
                  placeholder={t("newsletter.placeholder")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="flex-1"
                />
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t("newsletter.subscribing")}
                    </>
                  ) : (
                    t("newsletter.subscribe")
                  )}
                </Button>
              </form>
            </>
          )}
        </motion.div>

        <p className="mt-6 text-xs text-muted-foreground">
          No spam, unsubscribe at any time. Read our{" "}
          <a href="/privacy" className="underline underline-offset-2 hover:text-foreground">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </div>
  )
}
