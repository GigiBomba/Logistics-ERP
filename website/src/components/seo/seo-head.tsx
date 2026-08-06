import { Helmet } from "react-helmet-async"
import { seoConfig } from "@/config/site"
import { SUPPORTED_LOCALES } from "@/i18n/types"

export interface HreflangEntry {
  lang: string
  url: string
}

interface SeoHeadProps {
  title: string
  description: string
  canonical?: string
  ogImage?: string
  ogType?: string
  noindex?: boolean
  hreflang?: HreflangEntry[]
}

/**
 * Generate hreflang entries for all 6 supported locales pointing to the
 * current URL. Since this is an SPA without locale-specific URL paths,
 * all locale variants serve the same URL.
 */
function getDefaultHreflang(): HreflangEntry[] {
  const url = typeof window !== "undefined" ? window.location.origin + window.location.pathname : "https://operionerp.xyz"
  return SUPPORTED_LOCALES.map((l) => ({
    lang: l.code,
    url,
  }))
}

export function SeoHead({
  title,
  description,
  canonical,
  ogImage = "https://operionerp.xyz/logo3.png",
  ogType = "website",
  noindex = false,
  hreflang: explicitHreflang,
}: SeoHeadProps) {
  const fullTitle = title.includes("Operion") ? title : `${title} — Operion`
  const url = canonical || (typeof window !== "undefined" ? window.location.href : "https://operionerp.xyz")

  // Auto-generate hreflang unless explicit entries are provided
  const hreflangEntries = explicitHreflang ?? getDefaultHreflang()

  return (
    <Helmet>
      {/* Primary meta */}
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      {noindex && <meta name="robots" content="noindex, nofollow" />}
      <link rel="canonical" href={url} />

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:url" content={url} />
      <meta property="og:type" content={ogType} />
      <meta property="og:site_name" content={seoConfig.siteName} />
      <meta property="og:locale" content={seoConfig.locale} />

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={seoConfig.twitterHandle} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {/* Hreflang */}
      {hreflangEntries?.map((entry) => (
        <link
          key={entry.lang}
          rel="alternate"
          hrefLang={entry.lang}
          href={entry.url}
        />
      ))}
      {hreflangEntries && hreflangEntries.length > 0 && (
        <link rel="alternate" hrefLang="x-default" href={hreflangEntries.find((h) => h.lang === "en")?.url || url} />
      )}
    </Helmet>
  )
}
