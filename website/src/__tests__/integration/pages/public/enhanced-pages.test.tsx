import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import HomePage from "@/pages/public/home"
import FeaturesPage from "@/pages/public/features"
import PricingPage from "@/pages/public/pricing"
import DownloadPage from "@/pages/public/download"
import AboutPage from "@/pages/public/about"
import MissionPage from "@/pages/public/mission"
import FaqPage from "@/pages/public/faq"
import ContactPage from "@/pages/public/contact"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/config/site", () => ({
  siteConfig: {
    name: "Operion",
    tagline: "Enterprise Logistics Platform",
    description:
      "Operion ERP is a comprehensive logistics management platform for route planning, fleet management, dispatch, and enterprise operations.",
    url: "https://operion.com",
    ogImage: "/og-image.png",
    links: { twitter: "https://twitter.com/operion", github: "https://github.com/operion", linkedin: "https://linkedin.com/company/operion" },
  },
  apiConfig: { baseUrl: "http://localhost:8000", timeout: 15000 },
  downloadConfig: {
    latestVersion: "1.0.0",
    releaseDate: "2026-09-01",
    windowsInstaller: "/downloads/operion-setup-1.0.0.exe",
    fileSize: "245 MB",
    systemRequirements: {
      os: ["Windows 10 (64-bit)", "Windows 11 (64-bit)"],
      ram: "8 GB minimum (16 GB recommended)",
      storage: "2 GB available space",
      processor: "Intel Core i5 or equivalent",
      additional: ".NET Framework 4.8 or later",
    },
  },
  docsConfig: { readingSpeedWPM: 200, categories: [] },
  blogConfig: { postsPerPage: 9, featuredPostSlug: "complete-fleet-management-guide" },
  toolkitConfig: {
    latestVersion: "1.0.0",
    releaseDate: "2026-09-01",
    downloadUrl: "/downloads/operion-toolkit-1.0.0.exe",
  },
  analyticsConfig: { measurementId: "" },
  socialLinks: { twitter: "#", github: "#", linkedin: "#" },
  seoConfig: {
    defaultTitle: "Operion — Enterprise Logistics Platform",
    titleTemplate: "%s — Operion",
    defaultDescription: "Operion ERP is a comprehensive enterprise logistics platform.",
    twitterHandle: "@operion",
    siteName: "Operion",
    locale: "en_US",
  },
}))

describe("Enhanced pages - HomePage", () => {
  it("renders without crashing and shows sections", () => {
    render(<HomePage />)
    expect(screen.getByText("Enterprise Logistics,", { exact: false })).toBeInTheDocument()
    // Workflow section
    expect(screen.getByText("How It Works")).toBeInTheDocument()
    // FAQ preview
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FeaturesPage", () => {
  it("renders feature cards", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Route Planning & Optimization")).toBeInTheDocument()
    expect(screen.getByText("Fleet Management")).toBeInTheDocument()
  })
})

describe("Enhanced pages - PricingPage", () => {
  it("renders pricing page", () => {
    render(<PricingPage />)
    expect(screen.getByText("Simple, Transparent Pricing")).toBeInTheDocument()
  })
})

describe("Enhanced pages - DownloadPage", () => {
  it("renders download page", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Download Operion Desktop")).toBeInTheDocument()
  })
})

describe("Enhanced pages - AboutPage", () => {
  it("renders about page", () => {
    render(<AboutPage />)
    expect(screen.getByText("About Operion")).toBeInTheDocument()
  })
})

describe("Enhanced pages - MissionPage", () => {
  it("renders mission page", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Mission")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FaqPage", () => {
  it("renders faq page", () => {
    render(<FaqPage />)
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
  })
})

describe("Enhanced pages - ContactPage", () => {
  it("renders contact page", () => {
    render(<ContactPage />)
    expect(screen.getByText("Get in Touch")).toBeInTheDocument()
  })
})
