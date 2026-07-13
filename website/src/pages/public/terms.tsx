import { Helmet } from "react-helmet-async"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const sections = [
  {
    id: "acceptance",
    title: "1. Acceptance of Terms",
    content: "By accessing or using the Operion ERP platform, website, and desktop application (collectively, the 'Service'), you agree to be bound by these Terms of Service. If you are using the Service on behalf of an organization, you represent that you have the authority to bind that organization to these terms. If you do not agree to these terms, do not use the Service.",
  },
  {
    id: "account",
    title: "2. Account Registration & Security",
    content: "You must provide accurate and complete information when creating your account. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You must notify us immediately of any unauthorized use of your account. Operion reserves the right to suspend or terminate accounts that violate these terms.",
  },
  {
    id: "subscription",
    title: "3. Subscription & Payment Terms",
    content: "Operion offers subscription plans as described on our pricing page. Fees are billed in advance on a monthly or annual basis, depending on your selected plan. All fees are non-refundable except as required by law or as explicitly stated in our refund policy. We reserve the right to change pricing with 30 days' notice. Price changes will take effect at your next billing cycle.",
  },
  {
    id: "license",
    title: "4. License Grant & Restrictions",
    content: "Subject to your compliance with these terms and payment of applicable fees, Operion grants you a non-exclusive, non-transferable, limited license to install and use the desktop application for your internal business purposes. You may not: reverse engineer, decompile, or disassemble the software; rent, lease, or sublicense the Service; use the Service to build a competitive product; or exceed the usage limits specified in your subscription plan.",
  },
  {
    id: "acceptable-use",
    title: "5. Acceptable Use Policy",
    content: "You agree not to use the Service for any unlawful purpose or in violation of any applicable laws. You may not upload malicious code, attempt to gain unauthorized access to our systems, interfere with the Service's operation, or use the Service to transmit spam or unsolicited communications. Operion may investigate violations and cooperate with law enforcement authorities.",
  },
  {
    id: "intellectual-property",
    title: "6. Intellectual Property",
    content: "The Service, including all software, documentation, designs, and content, is owned by Operion and protected by copyright, trademark, and other intellectual property laws. These terms do not grant you any rights to our trademarks or branding. You retain all rights to the data you upload to the Service. By using the Service, you grant us a limited license to process your data as necessary to provide the Service.",
  },
  {
    id: "liability",
    title: "7. Limitation of Liability",
    content: "To the maximum extent permitted by applicable law, Operion shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of the Service. Our total liability for any claim arising from these terms shall not exceed the amount you paid us in the 12 months preceding the claim. Nothing in these terms limits liability for fraud, death, or personal injury caused by negligence.",
  },
  {
    id: "termination",
    title: "8. Termination",
    content: "You may terminate your account at any time through your account settings. Operion may terminate or suspend your account for breach of these terms, with notice where reasonably possible. Upon termination, your right to access the Service ceases immediately. We will retain your data for 30 days after termination to allow you to export it. After that period, your data will be permanently deleted.",
  },
  {
    id: "governing-law",
    title: "9. Governing Law",
    content: "These terms shall be governed by and construed in accordance with the laws of Romania, without regard to conflict of law principles. Any disputes arising from these terms shall be resolved in the courts of Bucharest, Romania. For consumers in the EU, you may also have rights under your local consumer protection laws.",
  },
  {
    id: "changes",
    title: "10. Changes to Terms",
    content: "We may modify these terms from time to time. Material changes will be communicated via email and in-app notification at least 30 days before they take effect. Your continued use of the Service after the effective date constitutes acceptance of the modified terms. If you do not agree to the changes, you must stop using the Service and terminate your account.",
  },
]

export default function TermsPage() {
  return (
    <>
      <Helmet>
        <title>Terms of Service — Operion ERP</title>
        <meta name="description" content="Operion ERP terms of service — subscription terms, license grants, acceptable use, and legal information." />
      </Helmet>
      <PageHeader title="Terms of Service" description="Last updated: July 2026" />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
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
