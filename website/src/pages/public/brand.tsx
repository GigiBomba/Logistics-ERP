import { motion } from "motion/react"
import { SeoHead } from "@/components/seo/seo-head"
import { useLocale } from "@/i18n/locale-context"
import { Download, Mail, Image, Type, Shapes, Check, X, AlertCircle } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CtaBanner } from "@/components/shared/cta-banner"
import { pressConfig } from "@/config/site"

const logoDoDonts = [
  {
    do: "Use the logo on a clean, contrasting background",
    dont: "Place the logo on busy or clashing backgrounds",
  },
  {
    do: "Maintain the minimum clear space around the logo",
    dont: "Stretch, distort, or rotate the logo",
  },
  {
    do: "Use approved color variations provided below",
    dont: "Change the logo colors outside the palette",
  },
]

const logoVariations = [
  {
    name: "Full Logo",
    description: "The complete Operion wordmark with icon. Use for headers, presentations, and primary branding.",
    format: "SVG, PNG, PDF",
  },
  {
    name: "Icon Only",
    description: "The Operion symbol alone. Ideal for favicons, app icons, and tight spaces.",
    format: "SVG, PNG, ICO",
  },
  {
    name: "Monochrome",
    description: "Single-color version for engraving, embroidery, and limited-color print.",
    format: "SVG, PNG, EPS",
  },
]

const colorPalette = [
  {
    name: "Operion Purple",
    hex: "#7C3AED",
    usage: "Primary brand color. Use for CTAs, key UI elements, and hero accents.",
    className: "bg-[#7C3AED]",
  },
  {
    name: "Deep Violet",
    hex: "#5B21B6",
    usage: "Dark variant for hover states, emphasis, and depth.",
    className: "bg-[#5B21B6]",
  },
  {
    name: "Soft Lavender",
    hex: "#DDD6FE",
    usage: "Background tints, subtle highlights, and card accents.",
    className: "bg-[#DDD6FE]",
    textClass: "text-foreground",
  },
  {
    name: "Neutral Slate",
    hex: "#64748B",
    usage: "Secondary text, icons, and supporting UI elements.",
    className: "bg-[#64748B]",
  },
  {
    name: "Charcoal",
    hex: "#1E293B",
    usage: "Headings, body text, and dark mode surfaces.",
    className: "bg-[#1E293B]",
  },
  {
    name: "Signal Amber",
    hex: "#F59E0B",
    usage: "Warnings, highlights, and attention-grabbing accents.",
    className: "bg-[#F59E0B]",
  },
]

const typeScale = [
  { weight: "400", label: "Regular", sample: "The quick brown fox jumps over the lazy dog." },
  { weight: "500", label: "Medium", sample: "The quick brown fox jumps over the lazy dog." },
  { weight: "600", label: "Semibold", sample: "The quick brown fox jumps over the lazy dog." },
  { weight: "700", label: "Bold", sample: "The quick brown fox jumps over the lazy dog." },
]

export default function BrandPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("brand.pageTitle")} description={t("brand.metaDesc")} canonical="https://operionerp.xyz/brand" />

      <HeroSection
        title={t("brand.title")}
        description={t("brand.heroDesc")}
        align="center"
        size="large"
      />

      {/* Our Logo */}
      <SectionWrapper>
        <SectionHeader
          title={t("brand.logo")}
          description={t("brand.logoDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <div className="rounded-2xl border bg-card p-12 text-center shadow-sm">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
              <Image className="h-10 w-10" />
            </div>
            <p className="mt-6 text-2xl font-bold tracking-tight">Operion</p>
            <p className="mt-1 text-sm text-muted-foreground">{t("brand.platformTagline")}</p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {logoDoDonts.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="space-y-3"
              >
                <div className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-300">
                  <Check className="h-4 w-4" />
                  <span>{t("brand.do")}</span>
                </div>
                <p className="text-sm text-muted-foreground">{item.do}</p>
                <div className="flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-300">
                  <X className="h-4 w-4" />
                  <span>{t("brand.dont")}</span>
                </div>
                <p className="text-sm text-muted-foreground">{item.dont}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Logo Variations */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("brand.variations")}
          description={t("brand.variationsDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {logoVariations.map((variant, i) => (
            <motion.div
              key={variant.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardHeader>
                  <div className="mb-4 flex h-24 items-center justify-center rounded-lg bg-muted">
                    <span className="text-2xl font-bold tracking-tight text-foreground">
                      {variant.name === "Icon Only" ? "◈" : "Operion"}
                    </span>
                  </div>
                  <CardTitle>{variant.name}</CardTitle>
                  <CardDescription>{variant.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">{variant.format}</span>
                    <Button variant="outline" size="sm">
                      <Download className="mr-2 h-3.5 w-3.5" />
                      {t("brand.downloadBtn")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Color Palette */}
      <SectionWrapper>
        <SectionHeader
          title={t("brand.colors")}
          description={t("brand.colorsDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {colorPalette.map((color, i) => (
            <motion.div
              key={color.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="overflow-hidden h-full">
                <div className={`h-24 w-full ${color.className} ${color.textClass ?? "text-white"} flex items-end p-4`}>
                  <span className="text-sm font-mono font-medium">{color.hex}</span>
                </div>
                <CardHeader>
                  <CardTitle className="text-base">{color.name}</CardTitle>
                  <CardDescription>{color.usage}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Typography */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("brand.typography")}
          description={t("brand.typographyDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl space-y-10"
        >
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Type className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">Inter</h3>
                  <p className="text-sm text-muted-foreground">{t("brand.interDesc")}</p>
                </div>
              </div>
              <div className="space-y-6">
                {typeScale.map((ts) => (
                  <div key={ts.weight} className="flex items-baseline gap-4">
                    <span className="w-20 text-xs font-mono text-muted-foreground">{ts.weight} — {ts.label}</span>
                    <p className="text-lg" style={{ fontWeight: Number(ts.weight) }}>{ts.sample}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Type className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">JetBrains Mono</h3>
                  <p className="text-sm text-muted-foreground">{t("brand.jetbrainsDesc")}</p>
                </div>
              </div>
              <div className="space-y-6 font-mono">
                {typeScale.map((ts) => (
                  <div key={ts.weight} className="flex items-baseline gap-4">
                    <span className="w-20 text-xs text-muted-foreground">{ts.weight}</span>
                    <p className="text-lg" style={{ fontWeight: Number(ts.weight) }}>{ts.sample}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Iconography */}
      <SectionWrapper>
        <SectionHeader
          title={t("brand.iconography")}
          description={t("brand.iconographyDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Shapes className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">Lucide React</h3>
                  <p className="text-sm text-muted-foreground">{t("brand.lucideDesc")}</p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t("brand.iconographyText")}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {["Navigation", "Actions", "Status", "Data"].map((tag) => (
                  <Badge key={tag} variant="secondary">{tag}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Downloads */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("brand.downloads")}
          description={t("brand.downloadsDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <Card className="border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background">
            <CardContent className="p-10">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Download className="h-8 w-8 text-primary" />
              </div>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("brand.completeKit")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {t("brand.completeKitDesc")}
              </p>
              <div className="mt-4 flex items-center justify-center gap-3 text-xs text-muted-foreground">
                <Badge variant="outline">.zip</Badge>
                <Badge variant="outline">12 MB</Badge>
                <Badge variant="outline">{t("brand.updatedDate")}</Badge>
              </div>
              <Button size="lg" className="mt-8">
                <Download className="mr-2 h-4 w-4" />
                {t("brand.downloadBtn")}
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Questions */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <AlertCircle className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">{t("brand.questions")}</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("brand.questionsDesc")}
          </p>
          <a
            href={`mailto:${pressConfig.contactEmail}`}
            className="mt-4 inline-flex items-center gap-2 text-sm font-medium underline underline-offset-4"
          >
            <Mail className="h-4 w-4" />
            {pressConfig.contactEmail}
          </a>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("brand.ctaTitle")}
          description={t("brand.ctaDesc")}
          buttonText={t("brand.ctaButton")}
          buttonHref="/partners"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
