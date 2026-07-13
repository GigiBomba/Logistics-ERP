import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Code2, BookOpen, ArrowRight } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export default function ApiPlaygroundPage() {
  return (
    <>
      <Helmet>
        <title>API Playground — Operion</title>
        <meta
          name="description"
          content="Interactive API documentation will be available when the public API is stabilized."
        />
      </Helmet>

      <HeroSection
        title="API Playground"
        description="Interactive API documentation will be available when the public API is stabilized. For now, explore our documentation."
        align="center"
        size="large"
      />

      <SectionWrapper className="pt-0">
        <div className="mx-auto max-w-2xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card>
              <CardContent className="flex flex-col items-center p-12 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
                  <Code2 className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight">Coming Soon</h2>
                <p className="mt-3 text-muted-foreground max-w-md">
                  We are actively developing our public API. The interactive playground will be
                  available once the API is stabilized and documented, so you can explore
                  endpoints, test requests, and inspect responses — all from your browser.
                </p>
                <Button size="lg" className="mt-8" asChild>
                  <a href="/docs">
                    <BookOpen className="mr-2 h-4 w-4" />
                    Browse Documentation
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </a>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
