import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface CookieEntry {
  name: string
  purpose: string
  duration: string
  category: "Strictly Necessary" | "Functional" | "Analytics" | "Marketing"
}

const cookies: CookieEntry[] = [
  { name: "csrf_token", purpose: "CSRF protection", duration: "Session", category: "Strictly Necessary" },
  { name: "operion-locale", purpose: "Language preference", duration: "1 year", category: "Functional" },
  { name: "operion-theme", purpose: "Theme preference", duration: "1 year", category: "Functional" },
  { name: "_ga", purpose: "Google Analytics", duration: "2 years", category: "Analytics" },
  { name: "_gid", purpose: "Google Analytics", duration: "24 hours", category: "Analytics" },
  { name: "_gat", purpose: "Google Analytics rate limiting", duration: "1 minute", category: "Analytics" },
  { name: "cf_clearance", purpose: "Cloudflare bot protection and Turnstile verification", duration: "30 minutes", category: "Strictly Necessary" },
  { name: "__cf_bm", purpose: "Cloudflare bot management", duration: "30 minutes", category: "Strictly Necessary" },
  { name: "operion_consent_v2", purpose: "Cookie consent preference", duration: "1 year", category: "Strictly Necessary" },
]

const categoryBadgeVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  "Strictly Necessary": "default",
  "Functional": "secondary",
  "Analytics": "outline",
  "Marketing": "destructive",
}

const tocItems = [
  { id: "what-are-cookies", title: "What Are Cookies" },
  { id: "how-we-use-cookies", title: "How We Use Cookies" },
  { id: "cookie-categories", title: "Cookie Categories" },
  { id: "cookie-list", title: "Cookie List" },
  { id: "third-party-services", title: "Third-Party Services" },
  { id: "managing-cookies", title: "Managing Cookies" },
  { id: "contact", title: "Contact" },
]

export default function CookiePolicyPage() {
  return (
    <>
      <SeoHead
        title="Cookie Policy — Operion ERP"
        description="Operion ERP cookie policy — how we use cookies, what data they collect, and how you can manage your preferences."
        canonical="https://operionerp.xyz/cookie-policy"
      />
      <PageHeader title="Cookie Policy" description="Last updated: July 2026" />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">Table of Contents</h2>
            <ul className="space-y-2">
              {tocItems.map((item) => (
                <li key={item.id}>
                  <a href={`#${item.id}`} className="text-sm text-primary hover:underline">
                    {item.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Content Sections */}
          <div className="space-y-10">
            {/* What Are Cookies */}
            <section id="what-are-cookies" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">What Are Cookies</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Cookies are small text files that are stored on your device when you visit a website. They
                are widely used to make websites work more efficiently, enhance user experience, and provide
                information to website owners. Cookies can be &ldquo;session&rdquo; cookies (temporary,
                deleted when you close your browser) or &ldquo;persistent&rdquo; cookies (remain on your
                device for a set period or until you delete them).
              </p>
            </section>

            {/* How We Use Cookies */}
            <section id="how-we-use-cookies" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">How We Use Cookies</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Operion uses cookies for several purposes: to ensure the security of your browsing session,
                to remember your preferences (such as language and theme settings), to analyze how visitors
                interact with our website so we can improve it, and to record your consent preferences. We
                do not use cookies for advertising or marketing purposes, and we never sell data collected
                through cookies to third parties.
              </p>
            </section>

            {/* Cookie Categories */}
            <section id="cookie-categories" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Cookie Categories</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                We classify the cookies used on our website into the following categories:
              </p>
              <div className="mt-6 grid gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="default">Strictly Necessary</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      These cookies are essential for the website to function properly. They enable core
                      functionality such as security, network management, and account access. The website
                      cannot function properly without these cookies, and they cannot be disabled in our
                      systems. They are usually set only in response to actions you take, such as logging
                      in or filling in forms.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="secondary">Functional</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Functional cookies enable the website to remember your preferences and choices (such
                      as your preferred language or theme) to provide a more personalized experience. These
                      cookies may be set by us or by third-party providers whose services we have added to
                      our pages. If you disable these cookies, some functionality may not work as intended.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="outline">Analytics</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Analytics cookies help us understand how visitors interact with our website by
                      collecting and reporting information anonymously. We use Google Analytics to analyse
                      page usage, traffic sources, and user behaviour patterns. This data helps us improve
                      our website content and user experience. These cookies do not identify you
                      personally.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="destructive">Marketing</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Operion does not currently use marketing or advertising cookies. This category will
                      be updated if we introduce any marketing-related tracking in the future. You will be
                      notified and asked for consent before any marketing cookies are placed on your
                      device.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* Cookie List */}
            <section id="cookie-list" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Cookie List</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                The following table lists the cookies that may be set when you visit our website:
              </p>
              <div className="mt-6 overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium">Cookie</th>
                      <th className="px-4 py-3 text-left font-medium">Purpose</th>
                      <th className="px-4 py-3 text-left font-medium">Duration</th>
                      <th className="px-4 py-3 text-left font-medium">Category</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cookies.map((cookie, i) => (
                      <tr key={cookie.name} className={i < cookies.length - 1 ? "border-b" : ""}>
                        <td className="px-4 py-3 font-mono text-xs">{cookie.name}</td>
                        <td className="px-4 py-3 text-muted-foreground">{cookie.purpose}</td>
                        <td className="px-4 py-3 text-muted-foreground">{cookie.duration}</td>
                        <td className="px-4 py-3">
                          <Badge variant={categoryBadgeVariant[cookie.category]}>
                            {cookie.category}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Third-Party Services */}
            <section id="third-party-services" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Third-Party Services</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                We rely on a small number of trusted third parties to operate and protect this
                website. Cloudflare, Inc. provides our content delivery network (CDN) and bot
                protection, including the Cloudflare Turnstile verification shown on our public
                forms. Google LLC provides Google Analytics, which helps us understand how
                visitors interact with our website. Data you submit through our website is
                transmitted to and processed by the Operion API service (api.operionerp.xyz).
                These providers process data under strict data processing agreements, and we do
                not sell data to any third party.
              </p>
            </section>

            {/* Managing Cookies */}
            <section id="managing-cookies" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Managing Cookies</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                You can control and manage cookies in several ways. Most browsers allow you to view, block,
                or delete cookies through your browser settings. Please note that blocking strictly necessary
                cookies may affect the functionality of our website. You can also withdraw your consent at
                any time by clicking the &ldquo;Cookie Preferences&rdquo; link in the footer of our website.
                For detailed instructions on managing cookies in your browser, visit aboutcookies.org.
              </p>
            </section>

            {/* Contact */}
            <section id="contact" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Contact</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                If you have any questions about our use of cookies or this policy, please contact us at{" "}
                <a href="mailto:support@operionerp.xyz" className="text-primary hover:underline">
                  support@operionerp.xyz
                </a>
                . You can also reach us by mail at Operion SRL, Bucharest, Romania.
              </p>
            </section>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
