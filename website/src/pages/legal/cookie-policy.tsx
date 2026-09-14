import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useLocale } from "@/i18n/locale-context"

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
  const { t } = useLocale()
  return (
    <>
      <SeoHead
        title={t("cookiePolicy.meta.title")}
        description={t("cookiePolicy.meta.description")}
        canonical="https://operionerp.xyz/cookie-policy"
      />
      <PageHeader title={t("cookiePolicy.pageTitle")} description={t("cookiePolicy.lastUpdated")} />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">{t("cookiePolicy.tableOfContents")}</h2>
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
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.whatAreCookies.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.whatAreCookies.content")}
              </p>
            </section>

            {/* How We Use Cookies */}
            <section id="how-we-use-cookies" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.howWeUseCookies.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.howWeUseCookies.content")}
              </p>
            </section>

            {/* Cookie Categories */}
            <section id="cookie-categories" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.cookieCategories.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.cookieCategories.intro")}
              </p>
              <div className="mt-6 grid gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="default">{t("cookiePolicy.category.strictlyNecessary.title")}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("cookiePolicy.category.strictlyNecessary.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="secondary">{t("cookiePolicy.category.functional.title")}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("cookiePolicy.category.functional.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="outline">{t("cookiePolicy.category.analytics.title")}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("cookiePolicy.category.analytics.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Badge variant="destructive">{t("cookiePolicy.category.marketing.title")}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("cookiePolicy.category.marketing.content")}
                    </p>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* Cookie List */}
            <section id="cookie-list" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.cookieList.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.cookieList.intro")}
              </p>
              <div className="mt-6 overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium">{t("cookiePolicy.table.header.cookie")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("cookiePolicy.table.header.purpose")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("cookiePolicy.table.header.duration")}</th>
                      <th className="px-4 py-3 text-left font-medium">{t("cookiePolicy.table.header.category")}</th>
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
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.thirdPartyServices.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.thirdPartyServices.content")}
              </p>
            </section>

            {/* Managing Cookies */}
            <section id="managing-cookies" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.managingCookies.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.managingCookies.content")}
              </p>
            </section>

            {/* Contact */}
            <section id="contact" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("cookiePolicy.section.contact.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("cookiePolicy.section.contact.contentA")}{" "}
                <a href="mailto:support@operionerp.xyz" className="text-primary hover:underline">
                  support@operionerp.xyz
                </a>
                {t("cookiePolicy.section.contact.contentB")}
              </p>
            </section>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
