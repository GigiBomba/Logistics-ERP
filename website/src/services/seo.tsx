import { Helmet } from "react-helmet-async"
import { seoConfig, siteConfig, socialLinks } from "@/config/site"

/**
 * Returns the full page title by applying the title template.
 * Example: getPageTitle("Features") → "Features — Operion"
 */
export function getPageTitle(title: string): string {
  return seoConfig.titleTemplate.replace("%s", title)
}

/**
 * Generates an array of standard meta tags for SEO and social sharing.
 * Pass page-specific overrides to customize per route.
 */
export interface MetaTag {
  name?: string
  property?: string
  content: string
}

export function generateMetaTags(options?: {
  title?: string
  description?: string
  image?: string
  url?: string
}): MetaTag[] {
  const pageTitle = options?.title ? getPageTitle(options.title) : seoConfig.defaultTitle
  const description = options?.description || seoConfig.defaultDescription
  const image = options?.image || siteConfig.ogImage
  const url = options?.url || siteConfig.url
  const absoluteImage = image.startsWith("http") ? image : `${siteConfig.url}${image}`

  return [
    { name: "description", content: description },
    { property: "og:title", content: pageTitle },
    { property: "og:description", content: description },
    { property: "og:image", content: absoluteImage },
    { property: "og:url", content: url },
    { property: "og:type", content: "website" },
    { property: "og:site_name", content: seoConfig.siteName },
    { property: "og:locale", content: seoConfig.locale },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:site", content: seoConfig.twitterHandle },
    { name: "twitter:title", content: pageTitle },
    { name: "twitter:description", content: description },
    { name: "twitter:image", content: absoluteImage },
  ]
}

/**
 * Renders JSON-LD structured data inside <Helmet> for the given schema type.
 * Use this component in page-level components to add semantic metadata.
 */
export function StructuredData({
  type,
  data,
}: {
  type: "Organization" | "WebSite" | "BreadcrumbList" | "Article"
  data?: Record<string, unknown>
}) {
  const schemas: Record<string, Record<string, unknown>> = {
    Organization: {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: siteConfig.name,
      url: siteConfig.url,
      logo: `${siteConfig.url}${siteConfig.ogImage}`,
      description: siteConfig.description,
      sameAs: [socialLinks.twitter, socialLinks.github, socialLinks.linkedin],
    },
    WebSite: {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: siteConfig.name,
      url: siteConfig.url,
      description: siteConfig.description,
    },
    BreadcrumbList: {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: data?.items || [],
    },
    Article: {
      "@context": "https://schema.org",
      "@type": "Article",
      ...(data || {}),
    },
  }

  const schema = schemas[type]

  return (
    <Helmet>
      <script type="application/ld+json">{JSON.stringify(schema)}</script>
    </Helmet>
  )
}
