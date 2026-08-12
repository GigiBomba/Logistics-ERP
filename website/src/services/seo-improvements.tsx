import { Helmet } from "react-helmet-async"
import { seoConfig, siteConfig } from "@/config/site"

// ─── SEOHelmet ──────────────────────────────────────────────

/**
 * SEOHelmet renders all standard meta tags pre-filled from seoConfig.
 * Use this as a drop-in replacement for raw <Helmet> in page layouts
 * to ensure consistent metadata across the site.
 */
export function SEOHelmet() {
  return (
    <Helmet>
      <html lang="en" />
      <title>{seoConfig.defaultTitle}</title>
      <meta name="description" content={seoConfig.defaultDescription} />
      <meta property="og:title" content={seoConfig.defaultTitle} />
      <meta property="og:description" content={seoConfig.defaultDescription} />
      <meta property="og:image" content={`${siteConfig.url}${siteConfig.ogImage}`} />
      <meta property="og:url" content={siteConfig.url} />
      <meta property="og:type" content="website" />
      <meta property="og:site_name" content={seoConfig.siteName} />
      <meta property="og:locale" content={seoConfig.locale} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={seoConfig.twitterHandle} />
      <meta name="twitter:title" content={seoConfig.defaultTitle} />
      <meta name="twitter:description" content={seoConfig.defaultDescription} />
      <meta name="twitter:image" content={`${siteConfig.url}${siteConfig.ogImage}`} />
      <link rel="canonical" href={siteConfig.url} />
    </Helmet>
  )
}

// ─── PageSEO ────────────────────────────────────────────────

interface PageSEOProps {
  title: string
  description: string
  ogImage?: string
  canonicalUrl?: string
  type?: "website" | "article" | "product" | "blog"
}

/**
 * PageSEO renders comprehensive SEO meta tags for a given page.
 * Uses seoConfig defaults for any omitted fields.
 *
 * @example
 * <PageSEO
 *   title="Features"
 *   description="Explore Operion's powerful logistics features."
 *   ogImage="/features-og.png"
 *   canonicalUrl="https://operionerp.xyz/features"
 *   type="website"
 * />
 */
export function PageSEO({
  title,
  description,
  ogImage,
  canonicalUrl,
  type = "website",
}: PageSEOProps) {
  const pageTitle = seoConfig.titleTemplate.replace("%s", title)
  const image = ogImage
    ? ogImage.startsWith("http")
      ? ogImage
      : `${siteConfig.url}${ogImage}`
    : `${siteConfig.url}${siteConfig.ogImage}`
  const canonical = canonicalUrl || `${siteConfig.url}/${title.toLowerCase().replace(/\s+/g, "-")}`

  return (
    <Helmet>
      <html lang="en" />
      <title>{pageTitle}</title>
      <meta name="description" content={description} />

      {/* Open Graph */}
      <meta property="og:title" content={pageTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={image} />
      <meta property="og:url" content={canonical} />
      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={seoConfig.siteName} />
      <meta property="og:locale" content={seoConfig.locale} />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={seoConfig.twitterHandle} />
      <meta name="twitter:title" content={pageTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />

      {/* Canonical */}
      <link rel="canonical" href={canonical} />
    </Helmet>
  )
}

// ─── generatePageMetaTags (utility, no JSX) ─────────────────

interface MetaTagInput {
  title?: string
  description?: string
  image?: string
  url?: string
}

/**
 * Returns an object of page metadata strings without rendering Helmet.
 * Useful for server-side or programmatic meta generation.
 */
export function getPageMeta(options?: MetaTagInput) {
  const pageTitle = options?.title
    ? seoConfig.titleTemplate.replace("%s", options.title)
    : seoConfig.defaultTitle
  const description = options?.description || seoConfig.defaultDescription
  const image = options?.image
    ? options.image.startsWith("http")
      ? options.image
      : `${siteConfig.url}${options.image}`
    : `${siteConfig.url}${siteConfig.ogImage}`
  const url = options?.url || siteConfig.url

  return { pageTitle, description, image, url }
}
