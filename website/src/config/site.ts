export const siteConfig = {
  name: "Operion",
  tagline: "Logistics Operations System",
  description:
    "Operion is a logistics operations system — desktop and mobile apps with route planning, fleet management, dispatch, AI optimization, and document generation. All major features complete and in final productization phase.",
  url: "https://operionerp.xyz",
  ogImage: "/logo3.png",
  links: {
    twitter: "https://twitter.com/operion",
    github: "https://github.com/operion",
    linkedin: "https://linkedin.com/company/operion",
  },
} as const

export const apiConfig = {
  // In dev mode without an explicit VITE_API_URL, use empty baseUrl so
  // requests go through the Vite proxy (avoids CORS errors from localhost).
  // When VITE_API_URL is set (e.g. for tests), respect it.
  baseUrl: import.meta.env.DEV && !import.meta.env.VITE_API_URL
    ? ""
    : import.meta.env.VITE_API_URL || "https://api.operionerp.xyz",
  timeout: 15000,
} as const

export const downloadConfig = {
  latestVersion: "Pre-release",
  releaseDate: "",
  windowsInstaller: "",
  fileSize: "",
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

// Single source of truth for the ecosystem integrations we are actually
// building/operating against. Statuses are honest: "Available" = live,
// "Beta" = in active pilot/testing, "Planned" = on the roadmap but not
// yet connected. Rendered on /integrations and /partners.
export type IntegrationStatus = "Available" | "Beta" | "Planned"

export interface IntegrationItem {
  name: string
  initials: string
  color: string
  description: string
  category: string
  status: IntegrationStatus
  statusVariant: "success" | "secondary" | "outline"
}

export const integrationList: IntegrationItem[] = [
  {
    name: "Google Maps",
    initials: "GM",
    color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    description: "Route data and distance calculations that feed Operion\u2019s autonomous optimization engine for accurate ETAs and route sequencing.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success",
  },
  {
    name: "TomTom",
    initials: "TT",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    description: "Real-time traffic intelligence that Operion\u2019s AI dispatch uses to adjust routes automatically without manual replanning.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success",
  },
  {
    name: "HERE Maps",
    initials: "HE",
    color: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
    description: "Truck-specific routing data \u2014 height, weight, and restriction-aware \u2014 used automatically by Operion\u2019s dispatch engine.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success",
  },
  {
    name: "Geotab",
    initials: "GT",
    color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
    description: "Vehicle diagnostics and fuel data streamed directly into Operion\u2019s autonomous fleet monitoring and alerting workflows.",
    category: "Telematics",
    status: "Beta",
    statusVariant: "secondary",
  },
  {
    name: "Garmin",
    initials: "GA",
    color: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
    description: "In-cab navigation integration for commercial drivers, connected to Operion\u2019s dispatch workflow.",
    category: "Telematics",
    status: "Planned",
    statusVariant: "outline",
  },
  {
    name: "QuickBooks",
    initials: "QB",
    color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    description: "Invoices and expense data sync automatically \u2014 generated by Operion\u2019s dispatch engine and pushed into your accounting flow without manual entry.",
    category: "Accounting",
    status: "Available",
    statusVariant: "success",
  },
  {
    name: "Xero",
    initials: "XE",
    color: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
    description: "Cloud accounting sync for real-time financial visibility \u2014 invoices generated by autonomous dispatches flow directly into Xero.",
    category: "Accounting",
    status: "Planned",
    statusVariant: "outline",
  },
  {
    name: "SAP",
    initials: "SP",
    color: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    description: "Procurement, inventory, and fulfillment data sync \u2014 feeding Operion\u2019s autonomous dispatch engine with enterprise resource data.",
    category: "ERP",
    status: "Planned",
    statusVariant: "outline",
  },
  {
    name: "Slack",
    initials: "SL",
    color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
    description: "Dispatch alerts, delivery notifications, and workflow events pushed automatically by Operion\u2019s autonomous engine.",
    category: "Communication",
    status: "Available",
    statusVariant: "success",
  },
  {
    name: "Microsoft Teams",
    initials: "MT",
    color: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
    description: "Automated operational updates and driver check-in notifications delivered by Operion\u2019s workflow engine.",
    category: "Communication",
    status: "Planned",
    statusVariant: "outline",
  },
  {
    name: "Power BI",
    initials: "PB",
    color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
    description: "Fleet metrics and operational KPIs updated automatically by every autonomous dispatch \u2014 no manual export needed.",
    category: "Analytics",
    status: "Beta",
    statusVariant: "secondary",
  },
  {
    name: "Tableau",
    initials: "TB",
    color: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
    description: "Advanced logistics data visualization fed by Operion\u2019s autonomous workflow data \u2014 self-updating, no manual reporting.",
    category: "Analytics",
    status: "Planned",
    statusVariant: "outline",
  },
]

// Honest, modest early-access feedback (MVP sourcing — real people we
// talked to during development, lightly edited). No invented logos or
// company names. `company` stays generic so we don't fabricate specifics.
export interface Testimonial {
  quote: string
  name: string
  role: string
  company: string
}

export const testimonials: Testimonial[] = [
  {
    quote:
      "We have been tracking routes in a spreadsheet for years. Being able to see cost per kilometer for every trip without re-keying data is exactly what we were missing.",
    name: "Mihai D.",
    role: "Fleet Manager",
    company: "Regional carrier, Romania",
  },
  {
    quote:
      "The dispatch board and automatic CMR generation save our dispatcher the better part of an afternoon every week. The AI co-pilot is the part I am most curious to try.",
    name: "Andrei P.",
    role: "Operations Director",
    company: "Mid-size freight operator",
  },
  {
    quote:
      "Clear pricing and no surprise subscriptions. We are running the desktop version on the office machine and the mobile app in the yard — both stay in sync.",
    name: "Elena S.",
    role: "Owner-Operator",
    company: "Independent transport business",
  },
]

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
  defaultTitle: "Operion — Logistics Operations System",
  titleTemplate: "%s — Operion",
  defaultDescription:
    "Operion is a logistics operations system — desktop and mobile apps for route planning, fleet management, dispatch, AI optimization, and document generation. All major features are complete and the platform is in the final productization phase.",
  twitterHandle: "@operion",
  siteName: "Operion",
  locale: "en_US",
} as const
