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

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    siteConfig: {
      name: "Operion",
      tagline: "Enterprise Logistics Platform",
      description:
        "Operion ERP is a comprehensive logistics management platform for route planning, fleet management, dispatch, and enterprise operations.",
      url: "https://operionerp.xyz",
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
  }
})

describe("Enhanced pages - HomePage", () => {
  it("renders without crashing and shows sections", () => {
    render(<HomePage />)
    expect(screen.getByText(/Logistics Operating System/)).toBeInTheDocument()
    // Stats section
    expect(screen.getByText("Autonomous Workflows")).toBeInTheDocument()
    expect(screen.getByText("Platform Apps")).toBeInTheDocument()
    // Workflow section
    expect(screen.getAllByText("From Intent to Execution").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("State Your Objective")).toBeInTheDocument()
    // Roadmap preview
    expect(screen.getByText("Autonomous Capabilities Roadmap")).toBeInTheDocument()
    // FAQ preview
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FeaturesPage", () => {
  it("renders features page", () => {
    render(<FeaturesPage />)
    expect(screen.getByText(/Autonomous Logistics Workflows/)).toBeInTheDocument()
    expect(screen.getByText("Autonomous Workflow FAQ")).toBeInTheDocument()
  })
})

describe("Enhanced pages - PricingPage", () => {
  it("renders pricing page", () => {
    render(<PricingPage />)
    expect(screen.getByText("Simple, Transparent Pricing")).toBeInTheDocument()
    expect(screen.getByText("Pricing FAQ")).toBeInTheDocument()
  })
})

describe("Enhanced pages - DownloadPage", () => {
  it("renders download page", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Download Operion Desktop")).toBeInTheDocument()
    expect(screen.getByText("System Requirements")).toBeInTheDocument()
  })
})

describe("Enhanced pages - AboutPage", () => {
  it("renders about page", () => {
    render(<AboutPage />)
    expect(screen.getByText("About Operion")).toBeInTheDocument()
    expect(screen.getByText("Company Timeline")).toBeInTheDocument()
  })
})

describe("Enhanced pages - MissionPage", () => {
  it("renders mission page", () => {
    render(<MissionPage />)
    expect(screen.getByText("Our Mission")).toBeInTheDocument()
    expect(screen.getByText("Our Vision")).toBeInTheDocument()
  })
})

describe("Enhanced pages - FaqPage", () => {
  it("renders category tabs", () => {
    render(<FaqPage />)
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
    // Category tabs
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
    // Contact methods
    expect(screen.getByText("Contact Methods")).toBeInTheDocument()
    expect(screen.getByText("Email Support")).toBeInTheDocument()
    // Form fields
    expect(screen.getByPlaceholderText("Your name")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("Tell us how we can help...")).toBeInTheDocument()
  })
})
