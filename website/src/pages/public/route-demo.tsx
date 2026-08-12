import { useState, useEffect, useRef } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, softwareApplicationSchema } from "@/components/seo/structured-data"
import { motion, AnimatePresence } from "motion/react"
import {
  MapPin,
  ArrowRight,
  Route,
  Clock,
  Fuel,
  Euro,
  TrendingUp,
  Zap,
  Calculator,
  AlertCircle,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { useLocale } from "@/i18n/locale-context"
import { trackCTAClick } from "@/services/analytics"
import apiClient from "@/api/client"

/* ─── Animated number helper ─── */
function useAnimatedNumber(target: number, duration = 800) {
  const [value, setValue] = useState(0)
  const startRef = useRef<number | null>(null)
  const fromRef = useRef(0)

  useEffect(() => {
    fromRef.current = value
    startRef.current = null
    let raf: number

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts
      const progress = Math.min((ts - startRef.current) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(fromRef.current + (target - fromRef.current) * eased))
      if (progress < 1) raf = requestAnimationFrame(step)
    }

    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])

  return value
}

interface RouteResult {
  distance: number
  etaHours: number
  fuelEstimate: number
  profitEstimate: number
  costEstimate: number
}

export default function RouteDemoPage() {
  const { t } = useLocale()
  const [origin, setOrigin] = useState("")
  const [destination, setDestination] = useState("")
  const [result, setResult] = useState<RouteResult | null>(null)
  const [isCalculating, setIsCalculating] = useState(false)
  const [error, setError] = useState("")

  const handleCalculate = async () => {
    if (!origin.trim() || !destination.trim()) return
    setIsCalculating(true)
    setResult(null)
    setError("")

    try {
      const { data } = await apiClient.post("/api/v1/route-demo/calculate", {
        origin: origin.trim(),
        destination: destination.trim(),
      }, { timeout: 30000 })

      if (!data || !data.distance_km) {
        throw new Error("Invalid response format")
      }

      setResult({
        distance: Math.round(data.distance_km),
        etaHours: parseFloat(data.duration_hours.toFixed(1)),
        fuelEstimate: data.fuelCost,
        profitEstimate: data.profit,
        costEstimate: data.totalCost,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Route calculation failed. Please try different cities.")
    } finally {
      setIsCalculating(false)
    }
  }

  const animatedDistance = useAnimatedNumber(result?.distance ?? 0)
  const animatedETA = useAnimatedNumber(Math.round((result?.etaHours ?? 0) * 10))
  const animatedFuel = useAnimatedNumber(result?.fuelEstimate ?? 0)
  const animatedProfit = useAnimatedNumber(result?.profitEstimate ?? 0)
  const animatedCost = useAnimatedNumber(result?.costEstimate ?? 0)

  return (
    <>
      <SeoHead title={t("routeDemo.pageTitle")} description={t("routeDemo.metaDesc")} canonical="https://operionerp.xyz/route-demo" />
      <JsonLd data={softwareApplicationSchema()} />

      <HeroSection
        title={t("routeDemo.title")}
        description={t("routeDemo.description")}
        align="center"
        size="large"
      />

      {/* Input Form */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Plan a Route"
          description="Enter your origin and destination to get a live route estimate."
          className="mb-10"
        />
        <Card className="mx-auto max-w-xl">
          <CardContent className="p-6 md:p-10">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("routeDemo.originCity")}</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder={t("routeDemo.originPlaceholder")}
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleCalculate()}
                    className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>

              <div className="flex items-center justify-center">
                <div className="rounded-full bg-accent p-1.5">
                  <ArrowRight className="h-4 w-4 text-primary rotate-90 sm:rotate-0" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">{t("routeDemo.destinationCity")}</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder={t("routeDemo.destinationPlaceholder")}
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleCalculate()}
                    className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>

              <Button
                className="w-full"
                size="lg"
                onClick={handleCalculate}
                disabled={!origin.trim() || !destination.trim() || isCalculating}
              >
                {isCalculating ? (
                  <>
                    <Zap className="mr-2 h-4 w-4 animate-pulse" />
                    {t("routeDemo.calculating")}
                  </>
                ) : (
                  <>
                    <Calculator className="mr-2 h-4 w-4" />
                    {t("routeDemo.calculate")}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
        {error && (
          <div className="mx-auto mt-4 max-w-xl rounded-lg border border-red-400 bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950/20 dark:text-red-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}
      </SectionWrapper>

      {/* Results */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <SectionWrapper>
              <SectionHeader
                title={t("routeDemo.title")}
                description={t("routeDemo.subtitle")}
                className="mb-10"
              />

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                >
                  <StatCard
                    value={`${animatedDistance.toLocaleString()} km`}
                    label={t("routeDemo.distance")}
                    icon={Route}
                  />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
                >
                  <StatCard
                    value={`${(animatedETA / 10).toFixed(1)} h`}
                    label={t("routeDemo.eta")}
                    icon={Clock}
                  />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
                >
                  <StatCard
                    value={`€${animatedFuel.toLocaleString()}`}
                    label={t("routeDemo.fuelEstimate")}
                    icon={Fuel}
                  />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
                >
                  <StatCard
                    value={`€${animatedProfit.toLocaleString()}`}
                    label={t("routeDemo.profitEstimate")}
                    icon={TrendingUp}
                  />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
                >
                  <StatCard
                    value={`€${animatedCost.toLocaleString()}`}
                    label={t("routeDemo.costEstimate")}
                    icon={Euro}
                  />
                </motion.div>
              </div>

              {/* Detailed breakdown */}
              <div className="mx-auto mt-12 max-w-lg">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("routeDemo.routeBreakdown")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {[
                      { label: t("routeDemo.distance"), value: `${result.distance} km` },
                      { label: t("routeDemo.eta"), value: `${result.etaHours} h` },
                      { label: t("routeDemo.fuelEstimate"), value: `€${result.fuelEstimate}` },
                      { label: t("routeDemo.profitEstimate"), value: `€${result.profitEstimate}` },
                      { label: t("routeDemo.costEstimate"), value: `€${result.costEstimate}` },
                    ].map((row) => (
                      <div key={row.label} className="flex items-center justify-between border-b pb-2 last:border-0 last:pb-0">
                        <span className="text-sm text-muted-foreground">{row.label}</span>
                        <span className="text-sm font-medium">{row.value}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </SectionWrapper>
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("routeDemo.tryForFree")}
          description={t("routeDemo.tryForFreeDesc")}
          buttonText={t("routeDemo.getStarted")}
          buttonHref="/register"
          variant="primary"
        />
      </SectionWrapper>

      {/* Powered by Operion ERP */}
      <SectionWrapper className="border-t bg-muted/30">
        <div className="mx-auto max-w-2xl text-center py-16">
          <h2 className="text-2xl font-bold tracking-tight">{t("routeDemo.poweredBy")}</h2>
          <p className="mt-4 text-muted-foreground leading-relaxed">
            {t("routeDemo.poweredByDesc")}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <a
              href="/waitlist"
              onClick={() => trackCTAClick("route_demo", "/route-demo")}
              className="inline-flex items-center rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              {t("routeDemo.joinWaitlist")}
            </a>
            <a
              href="/features"
              className="inline-flex items-center rounded-lg border px-6 py-3 text-sm font-medium hover:bg-accent transition-colors"
            >
              {t("routeDemo.exploreFeatures")}
            </a>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
