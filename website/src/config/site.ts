export const siteConfig = {
  name: "Operion",
  tagline: "Logistics Profit Calculator & ERP",
  description:
    "Operion is a logistics management application for trip profit calculation, route planning, fleet management, dispatch, and document generation.",
  url: "https://operion.com",
  ogImage: "/og-image.png",
  links: {
    twitter: "https://twitter.com/operion",
    github: "https://github.com/operion",
    linkedin: "https://linkedin.com/company/operion",
  },
} as const

export const apiConfig = {
  baseUrl: import.meta.env.VITE_API_URL || "https://api.operionerp.xyz",
  timeout: 15000,
} as const

export const downloadConfig = {
  latestVersion: "In Development",
  releaseDate: "",
  windowsInstaller: "",
  fileSize: "TBD",
  systemRequirements: {
    os: ["Windows 10 (64-bit)", "Windows 11 (64-bit)"],
    ram: "8 GB minimum (16 GB recommended)",
    storage: "2 GB available space",
    processor: "Intel Core i5 or equivalent",
    additional: "Python 3.10+",
  },
} as const

export const docsConfig = {
  readingSpeedWPM: 200,
  categories: [
    {
      id: "getting-started",
      title: "Getting Started",
      description: "Quick start guides and onboarding for Operion ERP",
      icon: "Rocket",
      slug: "/docs/getting-started",
    },
    {
      id: "core-concepts",
      title: "Core Concepts",
      description: "Understanding the Operion platform architecture",
      icon: "BookOpen",
      slug: "/docs/core-concepts",
    },
    {
      id: "route-planning",
      title: "Route Planning",
      description: "Optimize routes and delivery schedules",
      icon: "Map",
      slug: "/docs/route-planning",
    },
    {
      id: "fleet-management",
      title: "Fleet Management",
      description: "Manage your vehicle fleet and drivers",
      icon: "Truck",
      slug: "/docs/fleet-management",
    },
    {
      id: "dispatch",
      title: "Dispatch",
      description: "Real-time dispatch coordination and tracking",
      icon: "Radio",
      slug: "/docs/dispatch",
    },
    {
      id: "integrations",
      title: "Integrations",
      description: "Connect Operion with your existing tools",
      icon: "Puzzle",
      slug: "/docs/integrations",
    },
    {
      id: "api-reference",
      title: "API Reference",
      description: "Complete API documentation and code examples",
      icon: "Code",
      slug: "/docs/api-reference",
    },
  ],
} as const

export const blogConfig = {
  postsPerPage: 9,
  featuredPostSlug: "complete-fleet-management-guide",
} as const

export const toolkitConfig = {
  latestVersion: "1.0.0",
  releaseDate: "2026-09-01",
  downloadUrl: "/downloads/operion-toolkit-1.0.0.exe",
} as const

export const analyticsConfig = {
  measurementId: import.meta.env.VITE_GA_MEASUREMENT_ID || "",
} as const

export const socialLinks = {
  twitter: "https://twitter.com/operion",
  github: "https://github.com/operion",
  linkedin: "https://linkedin.com/company/operion",
} as const

export const enterpriseConfig = {
  contactEmail: "contact@operionerp.xyz",
} as const

export const partnerConfig = {
  contactEmail: "contact@operionerp.xyz",
} as const

export const careersConfig = {
  contactEmail: "contact@operionerp.xyz",
} as const

export const pressConfig = {
  contactEmail: "contact@operionerp.xyz",
  companyFacts: {
    founded: "2026",
    headquarters: "Romania",
  },
} as const

export const communityConfig = {
  discordInviteUrl: "https://discord.gg/operion",
  githubUrl: "https://github.com/operion",
} as const

export const seoConfig = {
  defaultTitle: "Operion — Logistics Profit Calculator & ERP",
  titleTemplate: "%s — Operion",
  defaultDescription:
    "Operion is a logistics management application for trip profit calculation, route planning, fleet management, dispatch operations, and document generation. Currently in active development.",
  twitterHandle: "@operion",
  siteName: "Operion",
  locale: "en_US",
} as const
