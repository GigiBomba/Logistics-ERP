import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date(date))
}

export function formatCurrency(amount: number, currency = "EUR"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount)
}

/**
 * Returns the first grapheme of a word, using Intl.Segmenter when available
 * (Unicode-aware, handles combining marks / emoji ZWJ sequences) and falling
 * back to code-point iteration (Array.from) otherwise.
 */
function firstGrapheme(word: string): string {
  if (!word) return ""
  const SegmenterCtor = (
    Intl as unknown as {
      Segmenter?: new (
        locales?: string | string[],
        options?: { granularity?: string }
      ) => { segment: (input: string) => Iterable<{ segment: string }> }
    }
  ).Segmenter
  if (typeof SegmenterCtor === "function") {
    const segmenter = new SegmenterCtor(undefined, { granularity: "grapheme" })
    for (const part of segmenter.segment(word)) {
      return part.segment
    }
    return ""
  }
  return Array.from(word)[0] ?? ""
}

/**
 * Computes avatar initials from a person or organization name.
 * Unicode-aware: handles diacritics and non-Latin scripts (Ștefan → "Ș", Ăgnes → "Ă").
 * Takes the first grapheme of the first two whitespace-separated words,
 * uppercases them, and falls back to "?" for empty/unusable input.
 */
export function getInitials(name: string): string {
  if (!name) return "?"
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  const first = firstGrapheme(words[0])
  const second = words.length > 1 ? firstGrapheme(words[1]) : ""
  const initials = `${first}${second}`.toUpperCase()
  return initials || "?"
}
