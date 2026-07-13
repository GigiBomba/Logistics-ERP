import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

export default function ChangelogPage() {
  return (
    <>
      <Helmet>
        <title>Changelog — Coming Soon | Operion</title>
        <meta name="description" content="Release notes for Operion ERP will appear here once the first public version ships." />
      </Helmet>

      <PageHeader
        title="Changelog"
        description="Track every update to the Operion platform."
      />

      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl py-20 text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight">Coming Soon</h2>
          <p className="mt-6 text-lg text-muted-foreground leading-relaxed">
            We're building something great. Release notes will appear here once the first public
            version ships.
          </p>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
