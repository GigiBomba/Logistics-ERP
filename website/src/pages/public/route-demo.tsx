import { useState, useEffect, useRef } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  MapPin,
  ArrowRight,
  Route,
  Clock,
  Fuel,
  Euro,
  TrendingUp,
  CheckCircle2,
  Zap,
  Calculator,
  AlertCircle,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { useLocale } from "@/i18n/locale-context"
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
  operionDistance: number
  operionEtaHours: number
  operionFuelEstimate: number
  operionProfitEstimate: number
  operionCostEstimate: number
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
      })

      const standard = data?.standard
      const optimized = data?.optimized
      if (!standard || !optimized) {
        throw new Error("Invalid response format")
      }

      setResult({
        distance: Math.round(standard.distance_km),
        etaHours: parseFloat(standard.duration_hours.toFixed(1)),
        fuelEstimate: standard.fuelCost,
        profitEstimate: standard.profit,
        costEstimate: standard.totalCost,
        operionDistance: Math.round(optimized.distance_km),
        operionEtaHours: parseFloat(optimized.duration_hours.toFixed(1)),
        operionFuelEstimate: optimized.fuelCost,
        operionProfitEstimate: optimized.profit,
        operionCostEstimate: optimized.totalCost,
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
      <Helmet>
        <title>{t("routeDemo.pageTitle")}</title>
        <meta
          name="description"
          content={t("routeDemo.metaDesc")}
        />
      </Helmet>

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
          description="Enter your origin and destination to get a live route comparison."
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

              {/* Comparison */}
              <div className="mt-12">
                <SectionHeader
                  title={t("routeDemo.operionTitle")}
                  description={t("routeDemo.comparisonDesc")}
                  className="mb-8"
                />
                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">{t("routeDemo.manual")}</Badge>
                        <CardTitle className="text-base">{t("routeDemo.standardRoute")}</CardTitle>
                      </div>
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

                  <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-primary/3 to-background">
                    <CardHeader>
                      <div className="flex items-center gap-2">
                        <Badge variant="default" className="text-[10px]">{t("routeDemo.operion")}</Badge>
                        <CardTitle className="text-base">{t("routeDemo.optimizedRoute")}</CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {[
                        { label: t("routeDemo.distance"), value: `${result.operionDistance} km`, diff: `-${Math.round((1 - result.operionDistance / result.distance) * 100)}%` },
                        { label: t("routeDemo.eta"), value: `${result.operionEtaHours} h`, diff: `-${((result.etaHours - result.operionEtaHours) / result.etaHours * 100).toFixed(0)}%` },
                        { label: t("routeDemo.fuelEstimate"), value: `€${result.operionFuelEstimate}`, diff: `-${Math.round((1 - result.operionFuelEstimate / result.fuelEstimate) * 100)}%` },
                        { label: t("routeDemo.profitEstimate"), value: `€${result.operionProfitEstimate}`, diff: `+${Math.round((result.operionProfitEstimate / result.profitEstimate - 1) * 100)}%` },
                        { label: t("routeDemo.costEstimate"), value: `€${result.operionCostEstimate}`, diff: `-${Math.round((1 - result.operionCostEstimate / result.costEstimate) * 100)}%` },
                      ].map((row) => (
                        <div key={row.label} className="flex items-center justify-between border-b pb-2 last:border-0 last:pb-0">
                          <span className="text-sm text-muted-foreground">{row.label}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{row.value}</span>
                            {row.diff && (
                              <span className="text-xs font-semibold text-green-600">{row.diff}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>

                <div className="mt-6 flex items-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span>
                    {t("routeDemo.savings")} ~12% {t("routeDemo.savingsDesc")}
                  </span>
                </div>
              </div>
            </SectionWrapper>
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title="Try Operion for free"
          description="Experience real route optimization on your actual fleet. No credit card required."
          buttonText="Get started"
          buttonHref="/register"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
