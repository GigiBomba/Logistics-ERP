import type { ReactElement } from "react"

interface JsonLdProps {
  data: Record<string, unknown>
}

export function JsonLd({ data }: JsonLdProps) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  )
}

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Operion",
    url: "https://operionerp.xyz",
    logo: "https://operionerp.xyz/logo3.png",
    description:
      "Operion is a logistics management application for trip profit calculation, route planning, fleet management, dispatch, and document generation.",
    email: "operion.contact@gmail.com",
    sameAs: [
      "https://twitter.com/operion",
      "https://github.com/operion",
      "https://linkedin.com/company/operion",
    ],
    foundingDate: "2026",
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer service",
      email: "operion.contact@gmail.com",
      availableLanguage: ["English"],
    },
  }
}

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Operion",
    url: "https://operionerp.xyz",
    description:
      "Operion is a logistics management application for trip profit calculation, route planning, fleet management, dispatch, and document generation.",
    potentialAction: {
      "@type": "SearchAction",
      target: "https://operionerp.xyz/search?q={search_term_string}",
      "query-input": "required name=search_term_string",
    },
  }
}

export function softwareApplicationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Operion",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows 10, Windows 11",
    description:
      "Desktop logistics management application for trip profit calculation, route planning, fleet management, dispatch, CMR document generation, and analytics for transport companies.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "EUR",
      description: "Free during productization phase — all major features complete",
    },
    softwareVersion: "0.1.0",
    datePublished: "2026-04",
    featureList: [
      "Trip Profit Calculator",
      "Route Planning with GraphHopper",
      "Fleet Management",
      "Driver Management",
      "Dispatch Board",
      "CMR Document Generation",
      "Invoice Generation",
      "Analytics Dashboard",
      "22 Language Support",
    ],
  }
}

export function faqSchema(items: Array<{ question: string; answer: string }>) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  }
}

export function breadcrumbSchema(
  items: Array<{ name: string; url: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  }
}

export function contactPageSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    name: "Contact Operion",
    url: "https://operionerp.xyz/contact",
    mainEntity: {
      "@type": "Organization",
      name: "Operion",
      email: "operion.contact@gmail.com",
      telephone: "+40-123-456-789",
    },
  }
}

export function articleSchema(params: {
  headline: string
  description: string
  url: string
  imageUrl: string
  datePublished: string
  dateModified?: string
  authorName: string
  publisherName?: string
  publisherLogoUrl?: string
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: params.headline,
    description: params.description,
    url: params.url,
    image: params.imageUrl,
    datePublished: params.datePublished,
    dateModified: params.dateModified || params.datePublished,
    author: {
      "@type": "Person",
      name: params.authorName,
    },
    publisher: {
      "@type": "Organization",
      name: params.publisherName || "Operion",
      logo: {
        "@type": "ImageObject",
        url: params.publisherLogoUrl || "https://operionerp.xyz/logo3.png",
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": params.url,
    },
  }
}

export function itemListSchema(params: {
  items: Array<{ title: string; url: string }>
  itemType?: string
}) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: params.items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.title,
      url: item.url,
    })),
  }
}

export function productSchema(params: {
  name: string
  description: string
  url: string
  price: string
  priceCurrency?: string
  category?: string
  offers?: Array<{ name: string; price: string; priceCurrency: string; description?: string }>
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: params.name,
    description: params.description,
    url: params.url,
    category: params.category || "BusinessApplication",
    offers: params.offers?.length
      ? params.offers.map((offer) => ({
          "@type": "Offer",
          name: offer.name,
          price: offer.price,
          priceCurrency: offer.priceCurrency,
          description: offer.description,
        }))
      : {
          "@type": "Offer",
          price: params.price,
          priceCurrency: params.priceCurrency || "EUR",
        },
  }
}

/**
 * Render multiple JSON-LD blocks in a single component.
 * Useful for pages that need e.g. BreadcrumbList + Article simultaneously.
 */
export function JsonLdMultiple({ schemas }: { schemas: Record<string, unknown>[] }): ReactElement {
  return (
    <>
      {schemas.map((schema, index) => (
        <JsonLd key={index} data={schema} />
      ))}
    </>
  )
}
