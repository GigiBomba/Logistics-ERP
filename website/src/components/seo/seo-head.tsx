import { Helmet } from "react-helmet-async"

interface SeoHeadProps {
  title: string
  description: string
  canonical?: string
  ogImage?: string
  ogType?: string
  noindex?: boolean
}

export function SeoHead({
  title,
  description,
  canonical,
  ogImage = "https://operion.com/og-image.png",
  ogType = "website",
  noindex = false,
}: SeoHeadProps) {
  const fullTitle = title.includes("Operion") ? title : `${title} — Operion`
  const url = canonical || (typeof window !== "undefined" ? window.location.href : "https://operion.com")

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      {noindex && <meta name="robots" content="noindex, nofollow" />}
      <link rel="canonical" href={url} />

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:url" content={url} />
      <meta property="og:type" content={ogType} />
      <meta property="og:site_name" content="Operion" />
      <meta property="og:locale" content="en_US" />

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@operion" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />
    </Helmet>
  )
}
