import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useLocale } from "@/i18n/locale-context"

const tocItems = [
  { id: "conformance-status", title: "Conformance Status" },
  { id: "what-weve-done", title: "Accessibility Features" },
  { id: "known-limitations", title: "Known Limitations" },
  { id: "testing-approach", title: "Testing Approach" },
  { id: "contact", title: "Contact" },
]

export default function AccessibilityStatementPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead
        title={t("accessibility.meta.title")}
        description={t("accessibility.meta.description")}
        canonical="https://operionerp.xyz/accessibility-statement"
      />
      <PageHeader title={t("accessibility.pageTitle")} description={t("accessibility.lastUpdated")} />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">{t("accessibility.tableOfContents")}</h2>
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
            {/* Conformance Status */}
            <section id="conformance-status" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("accessibility.section.conformanceStatus.title")}</h2>
              <div className="mt-3 space-y-3">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {t("accessibility.section.conformanceStatus.p1a")}{" "}
                  <a
                    href="https://www.w3.org/TR/WCAG21/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    {t("accessibility.section.conformanceStatus.link")}
                  </a>{" "}
                  {t("accessibility.section.conformanceStatus.p1b")}
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {t("accessibility.section.conformanceStatus.p2")}
                </p>
                <div className="mt-4">
                  <Badge variant="secondary" className="text-xs">
                    {t("accessibility.section.conformanceStatus.badge")}
                  </Badge>
                </div>
              </div>
            </section>

            {/* What We've Done */}
            <section id="what-weve-done" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("accessibility.section.whatWeveDone.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("accessibility.section.whatWeveDone.intro")}
              </p>
              <div className="mt-6 grid gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.keyboardNavigation.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.keyboardNavigation.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.screenReader.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.screenReader.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.focusIndicators.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.focusIndicators.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.colorContrast.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.colorContrast.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.responsive.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.responsive.content")}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>{t("accessibility.feature.altText.title")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("accessibility.feature.altText.content")}
                    </p>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* Known Limitations */}
            <section id="known-limitations" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("accessibility.section.knownLimitations.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("accessibility.section.knownLimitations.intro")}
              </p>
              <ul className="mt-4 list-disc pl-6 space-y-2 text-sm leading-relaxed text-muted-foreground">
                <li>
                  <strong>{t("accessibility.section.knownLimitations.thirdPartyTitle")}</strong>{" "}
                  {t("accessibility.section.knownLimitations.thirdPartyBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.knownLimitations.tablesTitle")}</strong>{" "}
                  {t("accessibility.section.knownLimitations.tablesBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.knownLimitations.browserTitle")}</strong>{" "}
                  {t("accessibility.section.knownLimitations.browserBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.knownLimitations.mediaTitle")}</strong>{" "}
                  {t("accessibility.section.knownLimitations.mediaBody")}
                </li>
              </ul>
            </section>

            {/* Testing Approach */}
            <section id="testing-approach" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("accessibility.section.testing.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("accessibility.section.testing.intro")}
              </p>
              <ul className="mt-4 list-disc pl-6 space-y-2 text-sm leading-relaxed text-muted-foreground">
                <li>
                  <strong>{t("accessibility.section.testing.axeCoreTitle")}</strong>{" "}
                  {t("accessibility.section.testing.axeCoreBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.testing.keyboardTitle")}</strong>{" "}
                  {t("accessibility.section.testing.keyboardBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.testing.screenReaderTitle")}</strong>{" "}
                  {t("accessibility.section.testing.screenReaderBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.testing.contrastTitle")}</strong>{" "}
                  {t("accessibility.section.testing.contrastBody")}
                </li>
                <li>
                  <strong>{t("accessibility.section.testing.reviewsTitle")}</strong>{" "}
                  {t("accessibility.section.testing.reviewsBody")}
                </li>
              </ul>
            </section>

            {/* Contact */}
            <section id="contact" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">{t("accessibility.section.contact.title")}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t("accessibility.section.contact.intro")}
              </p>
              <div className="mt-4 rounded-lg border bg-muted/30 p-4">
                <p className="text-sm font-medium">{t("accessibility.section.contact.contactLabel")}</p>
                <a
                  href="mailto:support@operionerp.xyz"
                  className="mt-1 block text-sm text-primary hover:underline"
                >
                  support@operionerp.xyz
                </a>
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("accessibility.section.contact.responseTime")}
                </p>
              </div>
            </section>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
