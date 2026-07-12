import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { ChevronRight } from "lucide-react"

const sections = [
  {
    id: "information-we-collect",
    title: "1. Information We Collect",
    content: `
      When you register for an Operion ERP account, we collect the information you provide directly: your full name, email address, company name, phone number, and billing details. This is necessary to create and maintain your account, process payments, and deliver our services.
      We also collect usage data automatically, including log files, device information, IP addresses, browser type, and interaction telemetry within the Operion desktop application. For fleet management functionality, we collect vehicle location data, route history, driver assignments, and operational metrics. Location data is collected only while the desktop application is active and is used exclusively for dispatch and route optimization purposes.
    `,
  },
  {
    id: "how-we-use-information",
    title: "2. How We Use Information",
    content: `
      We use the information we collect to operate, maintain, and improve Operion ERP. This includes providing real-time fleet tracking, generating operational reports, processing subscription payments, sending service-related communications, and offering technical support.
      We may also use aggregated, anonymized data to analyze usage trends, improve application performance, and develop new features. We will never use your data for advertising purposes or sell it to third parties. Communications regarding service updates, security notices, and support responses are considered part of the service and may be sent to the email address associated with your account.
    `,
  },
  {
    id: "data-storage-security",
    title: "3. Data Storage & Security",
    content: `
      All customer data is stored on servers located within the European Union, specifically in data centers in Frankfurt, Germany and Amsterdam, Netherlands. We employ AES-256 encryption for all data at rest and TLS 1.3 encryption for data in transit between the desktop application and our cloud infrastructure.
      We retain your account data for the duration of your subscription plus 90 days following termination, after which it is permanently deleted. Usage and telemetry data are retained in anonymized form for up to 24 months. Our security program includes quarterly penetration testing, annual SOC 2 audits, and continuous vulnerability scanning. Access to production systems is restricted to authorized personnel through multi-factor authentication and strict identity access management.
    `,
  },
  {
    id: "data-sharing",
    title: "4. Data Sharing",
    content: `
      Operion ERP does not sell your personal data. We share data only with trusted service providers who perform services on our behalf, such as payment processing (Stripe), cloud infrastructure (AWS), and email delivery (SendGrid). These providers are contractually bound to process data exclusively for the purposes we specify and in compliance with GDPR requirements.
      We may disclose your information if required to do so by law or in response to valid legal requests by public authorities. In the event of a merger, acquisition, or sale of assets, your data may be transferred as part of that transaction, and we will notify you via email and a prominent notice on our website.
    `,
  },
  {
    id: "your-rights",
    title: "5. Your Rights (GDPR)",
    content: `
      If you are located in the European Economic Area, you have the following rights under the General Data Protection Regulation (GDPR): the right to access your personal data, the right to rectify inaccurate data, the right to erasure ("right to be forgotten"), the right to restrict processing, the right to data portability, and the right to object to processing.
      To exercise any of these rights, please contact us at privacy@operion.com. We will respond to your request within 30 days. You also have the right to lodge a complaint with your local data protection authority if you believe we have not handled your data in compliance with applicable law.
    `,
  },
  {
    id: "cookies",
    title: "6. Cookies",
    content: `
      Operion ERP uses only functional cookies that are strictly necessary for the operation of our website and customer portal. These include session cookies for authentication, preference cookies to remember your language and theme settings, and security cookies to protect against fraudulent activity.
      We do not use tracking cookies, advertising cookies, or third-party analytics cookies on our website. The Operion desktop application does not use cookies at all. You may configure your browser to block or alert you about cookies, but this may affect the functionality of our customer portal.
    `,
  },
  {
    id: "contact",
    title: "7. Contact for Privacy Inquiries",
    content: `
      If you have any questions about this Privacy Policy or our data practices, please contact our Data Protection Officer at privacy@operion.com or by mail at: Operion ERP SRL, Data Protection Officer, 123 Victoriei Boulevard, Bucharest, 010081, Romania.
      We will acknowledge receipt of your inquiry within 48 hours and provide a substantive response within 30 days. We may request additional information to verify your identity before processing certain requests.
    `,
  },
]

export default function PrivacyPage() {
  return (
    <>
      <Helmet>
        <title>Privacy Policy - Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        <PageHeader
          title="Privacy Policy"
          description="Last updated: July 2026"
          className="text-center"
        />

        {/* Table of Contents */}
        <motion.nav
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
          className="mx-auto mt-12 max-w-3xl rounded-xl border bg-muted/30 p-6"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Table of Contents
          </h2>
          <ul className="mt-4 space-y-2">
            {sections.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="group inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ChevronRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                  {section.title}
                </a>
              </li>
            ))}
          </ul>
        </motion.nav>

        {/* Sections */}
        <div className="mx-auto mt-16 max-w-3xl space-y-16">
          {sections.map((section, index) => (
            <motion.section
              key={section.id}
              id={section.id}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="scroll-mt-24"
            >
              <h2 className="text-xl font-semibold tracking-tight text-foreground">
                {section.title}
              </h2>
              <div className="mt-4 space-y-4 text-sm leading-relaxed text-muted-foreground">
                {section.content
                  .trim()
                  .split("\n\n")
                  .map((paragraph, pIdx) => (
                    <p key={pIdx}>{paragraph.trim()}</p>
                  ))}
              </div>
              {index < sections.length - 1 && (
                <div className="mt-8 border-t border-border/40" />
              )}
            </motion.section>
          ))}
        </div>
      </SectionWrapper>
    </>
  )
}
