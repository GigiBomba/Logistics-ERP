import { useLocale } from "@/i18n/locale-context"
import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const sectionIds = [
  "informationCollection",
  "informationUse",
  "dataStorage",
  "dataSharing",
  "yourRights",
  "cookies",
  "contact",
] as const

export default function PrivacyPage() {
  const { t } = useLocale()

  const sections = sectionIds.map((id) => ({
    id: id.replace(/([A-Z])/g, "-$1").toLowerCase(),
    title: t(`privacy.section.${id}.title`),
    content: t(`privacy.section.${id}.content`),
  }))

  return (
    <>
      <SeoHead
        title={t("privacy.meta.title")}
        description={t("privacy.meta.description")}
        canonical="https://operionerp.xyz/privacy"
      />
      <PageHeader title={t("privacy.pageTitle")} description={t("privacy.lastUpdated")} />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">{t("privacy.tableOfContents")}</h2>
            <ul className="space-y-2">
              {sections.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className="text-sm text-primary hover:underline">{s.title}</a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Policy Sections */}
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
