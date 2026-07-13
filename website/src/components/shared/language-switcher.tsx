import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"
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
        variant="ghost"
        size="icon"
        onClick={() => setOpen(!open)}
        aria-label={`Change language (current: ${current.name})`}
        className="text-lg"
      >
        {current.flag}
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
              <div className="py-1">
                {SUPPORTED_LOCALES.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => { setLocale(lang.code); setOpen(false) }}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors hover:bg-accent",
                      locale === lang.code
                        ? "bg-accent text-accent-foreground font-medium"
                        : "text-foreground"
                    )}
                  >
                    <span className="text-base">{lang.flag}</span>
                    <span>{lang.nativeName}</span>
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
