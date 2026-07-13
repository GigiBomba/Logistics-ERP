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
  it("renders without crashing and shows V3 sections", () => {
    render(<HomePage />)
    expect(screen.getByText("Enterprise Logistics,", { exact: false })).toBeInTheDocument()
    expect(screen.getByText("Simplified")).toBeInTheDocument()
    // Stats section
    expect(screen.getByText("20+")).toBeInTheDocument()
    expect(screen.getByText("UI Views Built")).toBeInTheDocument()
    // Workflow section
    expect(screen.getByText("How It Works")).toBeInTheDocument()
    expect(screen.getByText("Calculate")).toBeInTheDocument()
    // Trust text
    expect(screen.getByText("Trusted by logistics teams worldwide")).toBeInTheDocument()
    // Roadmap preview
    expect(screen.getByText("What's Next")).toBeInTheDocument()
    // FAQ preview
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FeaturesPage", () => {
  it("renders comparison table section text", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("How Operion Compares")).toBeInTheDocument()
    // Table column labels
    expect(screen.getByText("Operion")).toBeInTheDocument()
    expect(screen.getByText("Traditional Solutions")).toBeInTheDocument()
    expect(screen.getByText("Manual Methods")).toBeInTheDocument()
    // A few feature rows from the comparison table
    expect(screen.getByText("Intelligent Route Optimization")).toBeInTheDocument()
    // "Real-Time GPS Tracking" appears in feature cards AND comparison table
    expect(screen.getAllByText("Real-Time GPS Tracking").length).toBeGreaterThanOrEqual(1)
    // FAQ
    expect(screen.getByText("Feature FAQ")).toBeInTheDocument()
  })
})

describe("Enhanced pages - PricingPage", () => {
  it("renders comparison table and pricing FAQ", () => {
    render(<PricingPage />)
    expect(screen.getByText("Plan Comparison")).toBeInTheDocument()
    // Column labels
    // "Starter" appears as both plan name and table column header
    expect(screen.getAllByText("Starter").length).toBeGreaterThanOrEqual(1)
    // "Professional" appears as plan name AND table column header
    expect(screen.getAllByText("Professional").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Enterprise").length).toBeGreaterThanOrEqual(1)
    // Pricing FAQ
    expect(screen.getByText("Pricing FAQ")).toBeInTheDocument()
    // FAQ questions
    expect(screen.getByText("Can I change plans at any time?")).toBeInTheDocument()
    expect(screen.getByText("Is there a free trial before I commit?")).toBeInTheDocument()
  })
})

describe("Enhanced pages - DownloadPage", () => {
  it("renders installation instructions and checksums", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Download Operion Desktop")).toBeInTheDocument()
    // Download button
    expect(screen.getByText("Download for Windows")).toBeInTheDocument()
    // Installation instructions
    expect(screen.getByText("Installation Instructions")).toBeInTheDocument()
    expect(screen.getByText("Download the Installer")).toBeInTheDocument()
    // Checksums
    expect(screen.getByText("File Checksums")).toBeInTheDocument()
    // A checksum hash value
    expect(screen.getByText(/e7b8c9a1f2d3e4f5/)).toBeInTheDocument()
    // System requirements
    expect(screen.getByText("System Requirements")).toBeInTheDocument()
  })
})

describe("Enhanced pages - AboutPage", () => {
  it("renders technology stack and timeline", () => {
    render(<AboutPage />)
    expect(screen.getByText("About Operion")).toBeInTheDocument()
    // Technology stack
    expect(screen.getByText("Technology Stack")).toBeInTheDocument()
    expect(screen.getByText("Python & PySide6")).toBeInTheDocument()
    expect(screen.getByText("SQLite Database")).toBeInTheDocument()
    // Timeline
    expect(screen.getByText("Company Timeline")).toBeInTheDocument()
    expect(screen.getByText("Project Started")).toBeInTheDocument()
    expect(screen.getByText("Architecture Refactoring")).toBeInTheDocument()
  })
})

describe("Enhanced pages - MissionPage", () => {
  it("renders vision section", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Mission")).toBeInTheDocument()
    expect(
      screen.getByText(/To make enterprise logistics accessible/)
    ).toBeInTheDocument()
    expect(screen.getByText("Our Vision")).toBeInTheDocument()
    expect(screen.getByText("What We Believe")).toBeInTheDocument()
    expect(screen.getByText("Core Values")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FaqPage", () => {
  it("renders category tabs", () => {
    render(<FaqPage />)
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
    // Category tabs - "General" appears as tab AND heading, use getAllByText
    const generalEls = screen.getAllByText("General")
    expect(generalEls.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Billing")).toBeInTheDocument()
    expect(screen.getByText("Technical")).toBeInTheDocument()
    expect(screen.getByText("Security")).toBeInTheDocument()
    // Search input
    expect(screen.getByPlaceholderText("Search frequently asked questions...")).toBeInTheDocument()
  })
})

describe("Enhanced pages - ContactPage", () => {
  it("renders contact methods", () => {
    render(<ContactPage />)
    expect(screen.getByText("Get in Touch")).toBeInTheDocument()
    // Contact info appears in sidebar AND contact methods section, use getAllByText
    const supportEmails = screen.getAllByText("operion.contact@gmail.com")
    expect(supportEmails.length).toBeGreaterThanOrEqual(1)
    // Contact methods section
    expect(screen.getByText("Contact Methods")).toBeInTheDocument()
    expect(screen.getByText("Email Support")).toBeInTheDocument()
    expect(screen.getByText("Phone Support")).toBeInTheDocument()
    // Form fields
    expect(screen.getByPlaceholderText("Your name")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("you@company.com")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("How can we help?")).toBeInTheDocument()
  })
})
