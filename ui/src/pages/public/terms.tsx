import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { ChevronRight } from "lucide-react"

const sections = [
  {
    id: "acceptance-of-terms",
    title: "1. Acceptance of Terms",
    content: `
      By accessing or using Operion ERP ("the Software"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to all of these Terms, you may not access or use the Software. These Terms constitute a legally binding agreement between you ("Customer") and Operion ERP SRL, a company registered in Romania.
      We reserve the right to update or modify these Terms at any time. Changes will be effective upon posting the revised Terms to our website. Your continued use of the Software after any such changes constitutes your acceptance of the new Terms. We will notify registered users of material changes via email at least 30 days before they take effect.
    `,
  },
  {
    id: "account-registration-security",
    title: "2. Account Registration & Security",
    content: `
      To use the Software, you must register for an account. You agree to provide accurate, current, and complete information during the registration process and to update such information as necessary. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.
      You must notify us immediately of any unauthorized use of your account or any other breach of security. We are not liable for any loss or damage arising from your failure to safeguard your password. Each account may be used by a single designated user; sharing credentials across multiple users is prohibited unless otherwise specified in your subscription plan.
    `,
  },
  {
    id: "subscription-payment",
    title: "3. Subscription & Payment Terms",
    content: `
      Operion ERP is offered on a subscription basis. Fees are billed in advance on a monthly or annual basis, as selected during registration. All prices are exclusive of applicable taxes, which will be added to your invoice. Payment is due at the start of each billing period and is processed through our secure payment gateway, Stripe.
      Subscriptions automatically renew at the end of each billing period unless cancelled at least 24 hours before the renewal date. You may cancel at any time from your account settings; cancellation takes effect at the end of the current billing period and no refunds are provided for partial periods. We reserve the right to change our pricing with 30 days' notice. Price changes apply at your next renewal date.
    `,
  },
  {
    id: "license-grant-restrictions",
    title: "4. License Grant & Restrictions",
    content: `
      Subject to your compliance with these Terms and payment of applicable fees, we grant you a limited, non-exclusive, non-transferable, revocable license to install and use the Operion ERP desktop application on devices owned or controlled by you, solely for your internal business operations. The number of permitted users and vehicles is determined by your subscription plan.
      You may not: (a) copy, modify, or create derivative works of the Software; (b) reverse engineer, decompile, or disassemble the Software; (c) rent, lease, sublicense, or transfer the Software to any third party; (d) use the Software in a manner that exceeds the scope of your subscription; or (e) remove or alter any proprietary notices or labels on the Software. All rights not expressly granted are reserved by Operion ERP SRL.
    `,
  },
  {
    id: "acceptable-use",
    title: "5. Acceptable Use Policy",
    content: `
      You agree to use Operion ERP in compliance with all applicable laws and regulations. You may not use the Software for any unlawful purpose, to transmit any harmful code, to interfere with the integrity or performance of the Software, or to attempt to gain unauthorized access to our systems or other users' accounts.
      You are solely responsible for the lawfulness of the data you input into the Software, including compliance with data protection regulations applicable to your fleet operations. We reserve the right to suspend or terminate access to the Software if we determine, in our reasonable judgment, that your use poses a security risk, violates these Terms, or could cause harm to us or third parties.
    `,
  },
  {
    id: "intellectual-property",
    title: "6. Intellectual Property",
    content: `
      Operion ERP, including its source code, design, graphics, user interface, and all related intellectual property rights, is the exclusive property of Operion ERP SRL and its licensors. The Operion name, logo, and product names are trademarks of Operion ERP SRL and may not be used without our prior written permission.
      You retain all intellectual property rights to the data you input into the Software ("Customer Data"). We do not claim ownership of your Customer Data. By using the Software, you grant us a limited license to process, store, and transmit your Customer Data solely for the purpose of providing the Software to you. We will never use your Customer Data for our own purposes or share it with third parties except as described in our Privacy Policy.
    `,
  },
  {
    id: "limitation-of-liability",
    title: "7. Limitation of Liability",
    content: `
      To the maximum extent permitted by applicable law, Operion ERP SRL shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including but not limited to loss of profits, data, use, or goodwill, arising out of or in connection with these Terms or the use of the Software, whether based on warranty, contract, tort (including negligence), or any other legal theory, even if we have been advised of the possibility of such damages.
      Our total aggregate liability arising out of or related to these Terms shall not exceed the amount paid by you during the twelve months preceding the event giving rise to the liability. This limitation of liability applies to the fullest extent permitted by law and shall survive any termination or expiration of these Terms. Some jurisdictions do not allow the exclusion or limitation of certain damages, so the above limitation may not apply to you.
    `,
  },
  {
    id: "termination",
    title: "8. Termination",
    content: `
      Either party may terminate these Terms at any time. You may terminate by cancelling your subscription and ceasing use of the Software. We may terminate or suspend your access to the Software immediately, without prior notice or liability, if you breach any provision of these Terms.
      Upon termination, your right to use the Software ceases immediately. We will provide you with a reasonable period, not exceeding 90 days, to export your Customer Data. After this period, your data will be permanently deleted from our systems in accordance with our data retention policy. Sections 6, 7, 9, and 10 of these Terms shall survive termination.
    `,
  },
  {
    id: "governing-law",
    title: "9. Governing Law",
    content: `
      These Terms shall be governed by and construed in accordance with the laws of Romania, without regard to its conflict of law provisions. The United Nations Convention on Contracts for the International Sale of Goods does not apply to these Terms.
      Any disputes arising out of or relating to these Terms or the Software shall be resolved exclusively in the courts of Bucharest, Romania. Notwithstanding the foregoing, we may seek injunctive or other equitable relief in any jurisdiction to protect our intellectual property rights. The prevailing party in any dispute shall be entitled to recover its reasonable legal fees and costs.
    `,
  },
  {
    id: "changes-to-terms",
    title: "10. Changes to Terms",
    content: `
      We reserve the right to modify these Terms at any time. When we make material changes, we will post the updated Terms on this page and notify registered users via email at least 30 days before the changes take effect. Your continued use of the Software after the effective date of the changes constitutes your acceptance of the modified Terms.
      If you do not agree to the modified Terms, you may terminate your subscription before the changes take effect. We encourage you to review these Terms periodically to stay informed about the terms that govern your use of Operion ERP. The date of the most recent revision is displayed at the top of this page.
    `,
  },
]

export default function TermsPage() {
  return (
    <>
      <Helmet>
        <title>Terms of Service - Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        <PageHeader
          title="Terms of Service"
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
