import { Helmet } from "react-helmet-async"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const sections = [
  {
    id: "information-collection",
    title: "1. Information We Collect",
    content: "We collect information you provide when creating an account, including your name, email address, and company details. When you use our desktop application, we collect usage data necessary to provide our services, including fleet location data for GPS tracking features. We also collect standard web analytics data when you visit our website, such as page views and browser information.",
  },
  {
    id: "information-use",
    title: "2. How We Use Information",
    content: "We use your information to deliver and improve our services, communicate with you about your account, and provide customer support. Location and fleet data is used exclusively for the logistics features you enable within the Operion platform. We may use anonymized, aggregated data for product improvement and industry analysis, but this data cannot be used to identify you or your company.",
  },
  {
    id: "data-storage",
    title: "3. Data Storage & Security",
    content: "Your data is stored on secure servers located within the European Union. We implement industry-standard security measures including AES-256 encryption at rest and TLS 1.3 for data in transit. We retain your data for as long as your account is active. Upon account termination, your data is permanently deleted within 90 days, unless retention is required by law.",
  },
  {
    id: "data-sharing",
    title: "4. Data Sharing",
    content: "We never sell your personal data or fleet operational data to third parties. We may share data with trusted service providers who assist us in operating our platform (such as cloud hosting providers), under strict data processing agreements. We may disclose information if required by law or to protect our legal rights.",
  },
  {
    id: "your-rights",
    title: "5. Your Rights",
    content: "Under GDPR and applicable data protection laws, you have the right to access, rectify, erase, and port your personal data. You may also object to or restrict certain processing activities. To exercise any of these rights, contact us at privacy@operion.com. We will respond to all legitimate requests within 30 days.",
  },
  {
    id: "cookies",
    title: "6. Cookies",
    content: "Our website uses only functional cookies necessary for authentication and session management. We do not use tracking cookies, advertising cookies, or third-party analytics cookies. You can configure your browser to reject cookies, but this may affect your ability to use certain features of our website.",
  },
  {
    id: "contact",
    title: "7. Contact Us",
    content: "For questions about this Privacy Policy or our data practices, contact our Data Protection Officer at privacy@operion.com or by mail at Operion SRL, Bucharest, Romania. You also have the right to lodge a complaint with your local data protection authority.",
  },
]

export default function PrivacyPage() {
  return (
    <>
      <Helmet>
        <title>Privacy Policy — Operion ERP</title>
        <meta name="description" content="Operion ERP privacy policy — how we collect, use, and protect your data." />
      </Helmet>
      <PageHeader title="Privacy Policy" description="Last updated: July 2026" />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">Table of Contents</h2>
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
