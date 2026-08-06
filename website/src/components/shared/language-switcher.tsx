import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"
import { Globe, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useLocale } from "@/i18n/locale-context"
import { SUPPORTED_LOCALES } from "@/i18n/types"
import { cn } from "@/lib/utils"

export function LanguageSwitcher() {
  const { locale, setLocale } = useLocale()
  const [open, setOpen] = useState(false)
  const current = SUPPORTED_LOCALES.find((l) => l.code === locale) || SUPPORTED_LOCALES[0]

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(!open)}
        aria-label={`Change language. Current: ${current.nativeName}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls="language-menu"
        className="h-8 px-2.5 rounded-full gap-1.5 text-xs font-semibold uppercase tracking-wide border-border/70 hover:bg-accent hover:border-accent"
      >
        <Globe className="h-3.5 w-3.5" />
        <span>{current.code.toUpperCase()}</span>
      </Button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -8 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full mt-2 z-50 w-48 rounded-lg border bg-popover shadow-lg overflow-hidden"
            >
              <div className="py-1" id="language-menu" role="listbox">
                {SUPPORTED_LOCALES.map((lang) => (
                  <button
                    key={lang.code}
                    role="option"
                    aria-selected={locale === lang.code}
                    onClick={() => { setLocale(lang.code); setOpen(false) }}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors hover:bg-accent focus:bg-accent focus:outline-none rounded-md",
                      locale === lang.code
                        ? "bg-accent text-accent-foreground font-medium"
                        : "text-foreground"
                    )}
                  >
                    <span className="text-base">{lang.flag}</span>
                    <span className="flex-1 text-left">{lang.nativeName}</span>
                    {locale === lang.code && <Check className="h-4 w-4" />}
                  </button>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
