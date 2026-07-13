import { lazy, Suspense, useEffect } from "react"
import { BrowserRouter, Routes, Route, useLocation } from "react-router"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute, AdminRoute } from "@/components/auth/protected-route"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { trackPageView } from "@/services/analytics"

// ─── Public Pages ──────────────────────────────────────────
const HomePage = lazy(() => import("@/pages/public/home"))
const FeaturesPage = lazy(() => import("@/pages/public/features"))
const PricingPage = lazy(() => import("@/pages/public/pricing"))
const DownloadPage = lazy(() => import("@/pages/public/download"))
const AboutPage = lazy(() => import("@/pages/public/about"))
const MissionPage = lazy(() => import("@/pages/public/mission"))
const FaqPage = lazy(() => import("@/pages/public/faq"))
const ContactPage = lazy(() => import("@/pages/public/contact"))
const PrivacyPage = lazy(() => import("@/pages/public/privacy"))
const TermsPage = lazy(() => import("@/pages/public/terms"))
const NotFoundPage = lazy(() => import("@/pages/public/not-found"))
const Error500Page = lazy(() => import("@/pages/public/error-500"))
const ErrorMaintenancePage = lazy(() => import("@/pages/public/error-maintenance"))
const ErrorOfflinePage = lazy(() => import("@/pages/public/error-offline"))
const BlogListPage = lazy(() => import("@/pages/public/blog-list"))
const BlogArticlePage = lazy(() => import("@/pages/public/blog-article"))
const BlogCategoryPage = lazy(() => import("@/pages/public/blog-category"))
const BlogAuthorPage = lazy(() => import("@/pages/public/blog-author"))
const TutorialsListPage = lazy(() => import("@/pages/public/tutorials-list"))
const TutorialDetailPage = lazy(() => import("@/pages/public/tutorial-detail"))
const ChangelogPage = lazy(() => import("@/pages/public/changelog"))
const RoadmapPage = lazy(() => import("@/pages/public/roadmap"))
const StatusPage = lazy(() => import("@/pages/public/status"))
const SecurityPage = lazy(() => import("@/pages/public/security"))
const DevelopersPage = lazy(() => import("@/pages/public/developers"))
const ToolkitPage = lazy(() => import("@/pages/public/toolkit"))
const IndustryTransportPage = lazy(() => import("@/pages/public/industry-transport"))
const IndustryFreightPage = lazy(() => import("@/pages/public/industry-freight"))
const IndustryFleetPage = lazy(() => import("@/pages/public/industry-fleet"))
const IndustryOwnerOpsPage = lazy(() => import("@/pages/public/industry-owner-ops"))
const IndustryAgriculturePage = lazy(() => import("@/pages/public/industry-agriculture"))
const IndustryConstructionPage = lazy(() => import("@/pages/public/industry-construction"))
const IndustryManufacturingPage = lazy(() => import("@/pages/public/industry-manufacturing"))
const ProductsPage = lazy(() => import("@/pages/public/products"))
const IntegrationsPage = lazy(() => import("@/pages/public/integrations"))
const CommunityPage = lazy(() => import("@/pages/public/community"))
const NewsletterPage = lazy(() => import("@/pages/public/newsletter"))
const CustomersPage = lazy(() => import("@/pages/public/customers"))
const CareersPage = lazy(() => import("@/pages/public/careers"))
const PressPage = lazy(() => import("@/pages/public/press"))
const BrandPage = lazy(() => import("@/pages/public/brand"))
const EnterprisePage = lazy(() => import("@/pages/public/enterprise"))
const PartnersPage = lazy(() => import("@/pages/public/partners"))
const TrustPage = lazy(() => import("@/pages/public/trust"))
const TrustCenterPage = lazy(() => import("@/pages/public/trust-center"))
const ApiPlaygroundPage = lazy(() => import("@/pages/public/api-playground"))
const IntegrationsExplorerPage = lazy(() => import("@/pages/public/integrations-explorer"))
const WaitlistPage = lazy(() => import("@/pages/public/waitlist"))
const ProductTourPage = lazy(() => import("@/pages/public/product-tour"))
const RoiCalculatorPage = lazy(() => import("@/pages/public/roi-calculator"))
const RouteDemoPage = lazy(() => import("@/pages/public/route-demo"))
const AdminBlogEditor = lazy(() => import("@/pages/admin/blog-editor"))
const AdminWaitlist = lazy(() => import("@/pages/admin/waitlist/admin-waitlist"))

// ─── Auth Pages ────────────────────────────────────────────
const LoginPage = lazy(() => import("@/pages/auth/login"))
const RegisterPage = lazy(() => import("@/pages/auth/register"))
const ForgotPasswordPage = lazy(() => import("@/pages/auth/forgot-password"))
const ResetPasswordPage = lazy(() => import("@/pages/auth/reset-password"))
const VerifyEmailPage = lazy(() => import("@/pages/auth/verify-email"))

// ─── Dashboard Pages ──────────────────────────────────────
const DashboardPage = lazy(() => import("@/pages/dashboard/dashboard"))
const ProfilePage = lazy(() => import("@/pages/dashboard/profile"))
const CompanyPage = lazy(() => import("@/pages/dashboard/company"))
const SubscriptionPage = lazy(() => import("@/pages/dashboard/subscription"))
const DashboardDownloadsPage = lazy(() => import("@/pages/dashboard/downloads"))
const DocumentationPage = lazy(() => import("@/pages/dashboard/documentation"))
const SupportPage = lazy(() => import("@/pages/dashboard/support"))
const SettingsPage = lazy(() => import("@/pages/dashboard/settings"))
const OrganizationsPage = lazy(() => import("@/pages/dashboard/organizations"))
const OrganizationSettingsPage = lazy(() => import("@/pages/dashboard/organization-settings"))
const LicensesPage = lazy(() => import("@/pages/dashboard/licenses"))
const OnboardingPage = lazy(() => import("@/pages/dashboard/onboarding"))
const BillingPage = lazy(() => import("@/pages/dashboard/billing"))

// ─── Docs Pages ────────────────────────────────────────────
const DocsLayout = lazy(() => import("@/pages/docs/docs-layout"))
const DocsCategoryPage = lazy(() => import("@/pages/docs/docs-category"))
const DocsArticlePage = lazy(() => import("@/pages/docs/docs-article"))

function PageSuspense() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  )
}

// ─── Page Tracker ─────────────────────────────────────────────
function PageTracker() {
  const location = useLocation()

  useEffect(() => {
    trackPageView(location.pathname)
  }, [location.pathname])

  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <PageTracker />
      <Routes>
        {/* Public pages with full shell */}
        <Route element={<AppShell />}>
          <Route
            index
            element={
              <Suspense fallback={<PageSuspense />}>
                <HomePage />
              </Suspense>
            }
          />
          <Route
            path="features"
            element={
              <Suspense fallback={<PageSuspense />}>
                <FeaturesPage />
              </Suspense>
            }
          />
          <Route
            path="pricing"
            element={
              <Suspense fallback={<PageSuspense />}>
                <PricingPage />
              </Suspense>
            }
          />
          <Route
            path="download"
            element={
              <Suspense fallback={<PageSuspense />}>
                <DownloadPage />
              </Suspense>
            }
          />
          <Route
            path="about"
            element={
              <Suspense fallback={<PageSuspense />}>
                <AboutPage />
              </Suspense>
            }
          />
          <Route
            path="mission"
            element={
              <Suspense fallback={<PageSuspense />}>
                <MissionPage />
              </Suspense>
            }
          />
          <Route
            path="faq"
            element={
              <Suspense fallback={<PageSuspense />}>
                <FaqPage />
              </Suspense>
            }
          />
          <Route
            path="contact"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ContactPage />
              </Suspense>
            }
          />
          <Route
            path="privacy"
            element={
              <Suspense fallback={<PageSuspense />}>
                <PrivacyPage />
              </Suspense>
            }
          />
          <Route
            path="terms"
            element={
              <Suspense fallback={<PageSuspense />}>
                <TermsPage />
              </Suspense>
            }
          />

          {/* Blog pages */}
          <Route
            path="blog"
            element={
              <Suspense fallback={<PageSuspense />}>
                <BlogListPage />
              </Suspense>
            }
          />
          <Route
            path="blog/:slug"
            element={
              <Suspense fallback={<PageSuspense />}>
                <BlogArticlePage />
              </Suspense>
            }
          />
          <Route
            path="blog/category/:category"
            element={
              <Suspense fallback={<PageSuspense />}>
                <BlogCategoryPage />
              </Suspense>
            }
          />
          <Route
            path="blog/author/:authorId"
            element={
              <Suspense fallback={<PageSuspense />}>
                <BlogAuthorPage />
              </Suspense>
            }
          />

          {/* Tutorials pages */}
          <Route
            path="tutorials"
            element={
              <Suspense fallback={<PageSuspense />}>
                <TutorialsListPage />
              </Suspense>
            }
          />
          <Route
            path="tutorials/:slug"
            element={
              <Suspense fallback={<PageSuspense />}>
                <TutorialDetailPage />
              </Suspense>
            }
          />

          {/* Changelog, Roadmap, Status */}
          <Route
            path="changelog"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ChangelogPage />
              </Suspense>
            }
          />
          <Route
            path="roadmap"
            element={
              <Suspense fallback={<PageSuspense />}>
                <RoadmapPage />
              </Suspense>
            }
          />
          <Route
            path="status"
            element={
              <Suspense fallback={<PageSuspense />}>
                <StatusPage />
              </Suspense>
            }
          />

          {/* Security & Developer pages */}
          <Route
            path="security"
            element={
              <Suspense fallback={<PageSuspense />}>
                <SecurityPage />
              </Suspense>
            }
          />
          <Route
            path="developers"
            element={
              <Suspense fallback={<PageSuspense />}>
                <DevelopersPage />
              </Suspense>
            }
          />
          <Route
            path="developers/toolkit"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ToolkitPage />
              </Suspense>
            }
          />

          {/* V3 Public Pages */}
          <Route
            path="products"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ProductsPage />
              </Suspense>
            }
          />
          <Route
            path="integrations"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IntegrationsPage />
              </Suspense>
            }
          />
          <Route
            path="community"
            element={
              <Suspense fallback={<PageSuspense />}>
                <CommunityPage />
              </Suspense>
            }
          />
          <Route
            path="newsletter"
            element={
              <Suspense fallback={<PageSuspense />}>
                <NewsletterPage />
              </Suspense>
            }
          />
          <Route
            path="customers"
            element={
              <Suspense fallback={<PageSuspense />}>
                <CustomersPage />
              </Suspense>
            }
          />
          <Route
            path="careers"
            element={
              <Suspense fallback={<PageSuspense />}>
                <CareersPage />
              </Suspense>
            }
          />
          <Route
            path="press"
            element={
              <Suspense fallback={<PageSuspense />}>
                <PressPage />
              </Suspense>
            }
          />
          <Route
            path="brand"
            element={
              <Suspense fallback={<PageSuspense />}>
                <BrandPage />
              </Suspense>
            }
          />
          <Route
            path="enterprise"
            element={
              <Suspense fallback={<PageSuspense />}>
                <EnterprisePage />
              </Suspense>
            }
          />
          <Route
            path="partners"
            element={
              <Suspense fallback={<PageSuspense />}>
                <PartnersPage />
              </Suspense>
            }
          />
          <Route
            path="trust"
            element={
              <Suspense fallback={<PageSuspense />}>
                <TrustPage />
              </Suspense>
            }
          />

          {/* Industry pages */}
          <Route
            path="industries/transport"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IndustryTransportPage />
              </Suspense>
            }
          />
          <Route
            path="industries/freight"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IndustryFreightPage />
              </Suspense>
            }
          />
          <Route
            path="industries/fleet"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IndustryFleetPage />
              </Suspense>
            }
          />
          <Route
            path="industries/owner-operators"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IndustryOwnerOpsPage />
              </Suspense>
            }
          />
          <Route
            path="industries/agriculture"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IndustryAgriculturePage />
              </Suspense>
            }
          />
          <Route
            path="industries/construction"
            element={
              <Suspense fallback={<PageSuspense />}>
                  <IndustryConstructionPage />
                </Suspense>
              }
            />
            <Route
              path="industries/manufacturing"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <IndustryManufacturingPage />
                </Suspense>
              }
            />
            <Route
              path="trust"
              element={
              <Suspense fallback={<PageSuspense />}>
                <TrustPage />
              </Suspense>
            }
          />
          <Route
            path="trust-center"
            element={
              <Suspense fallback={<PageSuspense />}>
                <TrustCenterPage />
              </Suspense>
            }
          />
          <Route
            path="api-playground"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ApiPlaygroundPage />
              </Suspense>
            }
          />
          <Route
            path="integrations-explorer"
            element={
              <Suspense fallback={<PageSuspense />}>
                <IntegrationsExplorerPage />
              </Suspense>
            }
          />
          <Route
            path="waitlist"
            element={
              <Suspense fallback={<PageSuspense />}>
                <WaitlistPage />
              </Suspense>
            }
          />

          {/* V4 Interactive Demos */}
          <Route
            path="product-tour"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ProductTourPage />
              </Suspense>
            }
          />
          <Route
            path="roi-calculator"
            element={
              <Suspense fallback={<PageSuspense />}>
                <RoiCalculatorPage />
              </Suspense>
            }
          />
          <Route
            path="route-demo"
            element={
              <Suspense fallback={<PageSuspense />}>
                <RouteDemoPage />
              </Suspense>
            }
          />

          {/* Auth pages */}
          <Route
            path="login"
            element={
              <Suspense fallback={<PageSuspense />}>
                <LoginPage />
              </Suspense>
            }
          />
          <Route
            path="register"
            element={
              <Suspense fallback={<PageSuspense />}>
                <RegisterPage />
              </Suspense>
            }
          />
          <Route
            path="forgot-password"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ForgotPasswordPage />
              </Suspense>
            }
          />
          <Route
            path="reset-password"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ResetPasswordPage />
              </Suspense>
            }
          />
          <Route
            path="verify-email"
            element={
              <Suspense fallback={<PageSuspense />}>
                <VerifyEmailPage />
              </Suspense>
            }
          />

          {/* Dashboard pages — protected */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="dashboard"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DashboardPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/profile"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <ProfilePage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/company"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <CompanyPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/subscription"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <SubscriptionPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/downloads"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DashboardDownloadsPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/docs"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DocumentationPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/support"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <SupportPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/settings"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <SettingsPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/organizations"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <OrganizationsPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/organizations/:slug/settings"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <OrganizationSettingsPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/licenses"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <LicensesPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/onboarding"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <OnboardingPage />
                </Suspense>
              }
            />
            <Route
              path="dashboard/billing"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <BillingPage />
                </Suspense>
              }
            />
          </Route>

          {/* Documentation pages */}
          <Route
            path="docs"
            element={
              <Suspense fallback={<PageSuspense />}>
                <DocsLayout />
              </Suspense>
            }
          >
            <Route
              index
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DocsCategoryPage />
                </Suspense>
              }
            />
            <Route
              path=":category"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DocsCategoryPage />
                </Suspense>
              }
            />
            <Route
              path=":category/:slug"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <DocsArticlePage />
                </Suspense>
              }
            />
          </Route>

          {/* Admin routes */}
          <Route element={<AdminRoute />}>
            <Route
              path="admin/blog/editor"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <AdminBlogEditor />
                </Suspense>
              }
            />
            <Route
              path="admin/blog/editor/:slug"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <AdminBlogEditor />
                </Suspense>
              }
            />
            <Route
              path="admin/waitlist"
              element={
                <Suspense fallback={<PageSuspense />}>
                  <AdminWaitlist />
                </Suspense>
              }
            />
          </Route>

          {/* Error pages */}
          <Route
            path="500"
            element={
              <Suspense fallback={<PageSuspense />}>
                <Error500Page />
              </Suspense>
            }
          />
          <Route
            path="maintenance"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ErrorMaintenancePage />
              </Suspense>
            }
          />
          <Route
            path="offline"
            element={
              <Suspense fallback={<PageSuspense />}>
                <ErrorOfflinePage />
              </Suspense>
            }
          />

          {/* 404 */}
          <Route
            path="*"
            element={
              <Suspense fallback={<PageSuspense />}>
                <NotFoundPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
