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
    url: "https://operion.com",
    logo: "https://operion.com/favicon.svg",
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
    url: "https://operion.com",
    description:
      "Operion is a logistics management application for trip profit calculation, route planning, fleet management, dispatch, and document generation.",
    potentialAction: {
      "@type": "SearchAction",
      target: "https://operion.com/search?q={search_term_string}",
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
      description: "Free during development phase",
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
    url: "https://operion.com/contact",
    mainEntity: {
      "@type": "Organization",
      name: "Operion",
      email: "operion.contact@gmail.com",
      telephone: "+40-123-456-789",
    },
  }
}
