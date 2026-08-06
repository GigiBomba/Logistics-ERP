import { useLocale } from "@/i18n/locale-context"
import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const sectionIds = [
  "acceptance",
  "account",
  "subscription",
  "license",
  "acceptableUse",
  "intellectualProperty",
  "liability",
  "termination",
  "governingLaw",
  "changes",
] as const

export default function TermsPage() {
  const { t } = useLocale()

  const sections = sectionIds.map((id) => ({
    id: id.replace(/([A-Z])/g, "-$1").toLowerCase(),
    title: t(`terms.section.${id}.title`),
    content: t(`terms.section.${id}.content`),
  }))

  return (
    <>
      <SeoHead
        title={t("terms.meta.title")}
        description={t("terms.meta.description")}
        canonical="https://operionerp.xyz/terms"
      />
      <PageHeader title={t("terms.pageTitle")} description={t("terms.lastUpdated")} />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">{t("terms.tableOfContents")}</h2>
            <ul className="space-y-2">
              {sections.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className="text-sm text-primary hover:underline">{s.title}</a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="space-y-10">
            {sections.map((s) => (
              <section key={s.id} id={s.id} className="scroll-mt-20">
                <h2 className="text-lg font-semibold">{s.title}</h2>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.content}</p>
              </section>
            ))}
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
