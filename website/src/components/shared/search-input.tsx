"use client"

import { Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"

interface SearchInputProps {
  placeholder?: string
  value: string
  onChange: (value: string) => void
  onClear?: () => void
  className?: string
}

export function SearchInput({
  placeholder = "Search...",
  value,
  onChange,
  onClear,
  className,
}: SearchInputProps) {
  const { t } = useLocale()
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 pl-9 text-sm ring-offset-background",
          "placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium",
          value && "pr-9"
        )}
      />
      {value && (
        <button
          type="button"
          onClick={() => {
            onChange("")
            onClear?.()
          }}
          className={cn(
            "absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1",
            "text-muted-foreground transition-colors hover:text-foreground"
          )}
          aria-label={t("common.aria.clearSearch")}
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
