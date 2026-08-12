import { useState, useEffect, useRef } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, softwareApplicationSchema } from "@/components/seo/structured-data"
import { motion, AnimatePresence } from "motion/react"
import {
  Clock,
  Fuel,
  Users,
  FileText,
  TrendingUp,
  Calculator,
  ChevronDown,
  ChevronUp,
  Info,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { StatCard } from "@/components/shared/stat-card"
import { useLocale } from "@/i18n/locale-context"
import { trackCTAClick } from "@/services/analytics"

/* ─── Animated number helper ─── */
function useAnimatedNumber(target: number, duration = 900) {
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

/* ─── Input row component ─── */
function InputRow({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  type = "number",
}: {
  label: string
  value: number
  onChange: (val: number) => void
  min: number
  max: number
  step?: number
  unit?: string
  type?: "number" | "slider"
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">{label}</label>
        <span className="text-sm font-semibold tabular-nums">
          {value.toLocaleString()}
          {unit ? ` ${unit}` : ""}
        </span>
      </div>
      {type === "slider" ? (
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full accent-primary"
        />
      ) : (
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
        />
      )}
    </div>
  )
}

export default function RoiCalculatorPage() {
  const { t } = useLocale()
  const [fleetSize, setFleetSize] = useState(20)
  const [drivers, setDrivers] = useState(18)
  const [monthlyTrips, setMonthlyTrips] = useState(450)
  const [avgRevenue, setAvgRevenue] = useState(280)
  const [avgFuelCost, setAvgFuelCost] = useState(45)
  const [avgDistancePerTrip, setAvgDistancePerTrip] = useState(350)
  const [dispatchers, setDispatchers] = useState(3)
  const [monthlyInvoices, setMonthlyInvoices] = useState(120)
  const [showAssumptions, setShowAssumptions] = useState(false)

  /* ─── Cost constants (TripCalculator) ─── */
  const DEFAULT_DRIVER_SALARY = 100
  const DEFAULT_TOLL_RATE = 0.22
  const EXTRA_COST_PER_KM = 0.03
  const EXTRA_COST_PER_DAY = 12
  const FUEL_PRICE = 1.65
  const TRUCK_CONSUMPTION = 32

  /* Per-trip cost breakdown
     Note: avgFuelCost input is provided by the user but we calculate fuel cost
     from distance + consumption for consistency with the TripCalculator model. */
  const fuelCostPerTrip = (avgDistancePerTrip / 100) * TRUCK_CONSUMPTION * FUEL_PRICE
  const tollCostPerTrip = avgDistancePerTrip * DEFAULT_TOLL_RATE
  const salaryCostPerTrip = DEFAULT_DRIVER_SALARY
  const extraCostPerTrip = avgDistancePerTrip * EXTRA_COST_PER_KM + EXTRA_COST_PER_DAY
  const totalCostPerTrip = fuelCostPerTrip + tollCostPerTrip + salaryCostPerTrip + extraCostPerTrip
  const profitPerTrip = avgRevenue - totalCostPerTrip
  const monthlyProfit = monthlyTrips * profitPerTrip

  /* Operion savings per month */
  const FUEL_SAVINGS_RATE = 0.12
  const TOLL_SAVINGS_RATE = 0.08
  const COORDINATION_TIME_PER_TRIP_HOURS = 0.5 // 30 min manual coordination per trip
  const TIME_SAVINGS_RATE = 0.9 // 90% reduction through dispatch automation
  const HOURS_PER_DISPATCHER_SAVED = 144 // ~6.5 h/day × 22 days – nearly full day saved per dispatcher
  const INVOICE_SAVING_PER_INVOICE = 2

  const fuelSavingsPerMonth = monthlyTrips * fuelCostPerTrip * FUEL_SAVINGS_RATE
  const tollSavingsPerMonth = monthlyTrips * tollCostPerTrip * TOLL_SAVINGS_RATE
  const hourlyDriverCost = DEFAULT_DRIVER_SALARY / 9

  /* Time savings:
     Each driver saves COORDINATION_TIME_PER_TRIP_HOURS of manual coordination
     per trip, reduced by TIME_SAVINGS_RATE through automation.
     Total = trips × hours/trip × savings_rate.
     With defaults: 450 × 0.5 × 0.9 = 202.5 h/month ≈ 203 h displayed. */
  const timeSavedHours = monthlyTrips * COORDINATION_TIME_PER_TRIP_HOURS * TIME_SAVINGS_RATE
  const timeSavingsPerMonth = timeSavedHours * hourlyDriverCost

  const adminSavingsPerMonth = dispatchers * HOURS_PER_DISPATCHER_SAVED * hourlyDriverCost
  const invoiceSavingsPerMonth = monthlyInvoices * INVOICE_SAVING_PER_INVOICE

  const totalMonthlySavings = fuelSavingsPerMonth + tollSavingsPerMonth + timeSavingsPerMonth + adminSavingsPerMonth + invoiceSavingsPerMonth
  const totalYearlySavings = totalMonthlySavings * 12

  /* Animated display values */
  const animatedCostPerTrip = useAnimatedNumber(Math.round(totalCostPerTrip))
  const animatedProfitPerTrip = useAnimatedNumber(Math.round(profitPerTrip))
  const animatedMonthlyProfit = useAnimatedNumber(Math.round(monthlyProfit))
  const animatedFuelSavings = useAnimatedNumber(Math.round(fuelSavingsPerMonth + tollSavingsPerMonth))
  const animatedTimeSavedHours = useAnimatedNumber(Math.round(timeSavedHours))
  const animatedAdminSavings = useAnimatedNumber(Math.round(adminSavingsPerMonth + invoiceSavingsPerMonth))
  const animatedMonthlySavings = useAnimatedNumber(Math.round(totalMonthlySavings))
  const animatedYearlySavings = useAnimatedNumber(Math.round(totalYearlySavings))

  return (
    <>
      <SeoHead title={t("roiCalculator.pageTitle")} description={t("roiCalculator.metaDesc")} canonical="https://operionerp.xyz/roi-calculator" />

      <JsonLd data={softwareApplicationSchema()} />

      <HeroSection
        title={t("roiCalculator.title")}
        description={t("roiCalculator.description")}
        align="center"
        size="large"
      />

      {/* Inputs */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Fleet Details"
          description="Enter your current operation numbers. Results update automatically."
          className="mb-10"
        />
        <Card className="mx-auto max-w-3xl">
          <CardContent className="p-6 md:p-10">
            <div className="grid gap-8 sm:grid-cols-2">
              <InputRow
                label={t("roiCalculator.fleetSize")}
                value={fleetSize}
                onChange={setFleetSize}
                min={1}
                max={500}
                type="slider"
                unit="vehicles"
              />
              <InputRow
                label={t("roiCalculator.numDrivers")}
                value={drivers}
                onChange={setDrivers}
                min={1}
                max={500}
                unit="drivers"
              />
              <InputRow
                label={t("roiCalculator.monthlyTrips")}
                value={monthlyTrips}
                onChange={setMonthlyTrips}
                min={1}
                max={5000}
                unit="trips"
              />
              <InputRow
                label={t("roiCalculator.avgRevenue")}
                value={avgRevenue}
                onChange={setAvgRevenue}
                min={10}
                max={5000}
                step={10}
                unit="EUR"
              />
              <InputRow
                label={t("roiCalculator.fuelCost")}
                value={avgFuelCost}
                onChange={setAvgFuelCost}
                min={5}
                max={500}
                step={5}
                unit="EUR"
              />
              <InputRow
                label={t("roiCalculator.avgDistance")}
                value={avgDistancePerTrip}
                onChange={setAvgDistancePerTrip}
                min={50}
                max={2000}
                step={10}
                unit="km"
              />
              <InputRow
                label="Number of dispatchers"
                value={dispatchers}
                onChange={setDispatchers}
                min={0}
                max={50}
                unit="dispatchers"
              />
              <InputRow
                label="Monthly invoices"
                value={monthlyInvoices}
                onChange={setMonthlyInvoices}
                min={0}
                max={1000}
                unit="invoices"
              />
            </div>
          </CardContent>
        </Card>
      </SectionWrapper>

      {/* Results */}
      <SectionWrapper>
        <SectionHeader
          title={t("roiCalculator.results")}
          description={t("roiCalculator.resultsDesc")}
          className="mb-10"
        />
        {/* Row 1 — Current Operation Summary */}
        <div className="mb-4 grid gap-4 sm:grid-cols-3">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedCostPerTrip.toLocaleString()}`}
              label={t("roiCalculator.avgCostTrip")}
              icon={FileText}
              trend={{ direction: "up", value: "Cost breakdown" }}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedProfitPerTrip.toLocaleString()}`}
              label={t("roiCalculator.avgProfitTrip")}
              icon={TrendingUp}
              trend={{ direction: "up", value: "Per-trip margin" }}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedMonthlyProfit.toLocaleString()}`}
              label={t("roiCalculator.monthlyProfit")}
              icon={Calculator}
              trend={{ direction: "up", value: "Current operations" }}
            />
          </motion.div>
        </div>

        {/* Row 2 — Operion Savings */}
        <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedFuelSavings.toLocaleString()}`}
              label={t("roiCalculator.fuelSavings")}
              icon={Fuel}
              trend={{ direction: "up", value: "Route optimization" }}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`${animatedTimeSavedHours.toLocaleString()} h`}
              label={t("roiCalculator.timeSavings")}
              icon={Clock}
              trend={{ direction: "up", value: "Dispatch automation" }}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedAdminSavings.toLocaleString()}`}
              label={t("roiCalculator.adminSavings")}
              icon={Users}
              trend={{ direction: "up", value: "Automation" }}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedMonthlySavings.toLocaleString()}`}
              label={t("roiCalculator.totalMonthlyRoi")}
              icon={TrendingUp}
              trend={{ direction: "up", value: "Combined savings" }}
            />
          </motion.div>
        </div>

        {/* Row 3 — Annual projection */}
        <div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <StatCard
              value={`€${animatedYearlySavings.toLocaleString()}`}
              label={t("roiCalculator.yearlySavings")}
              icon={Calculator}
              trend={{ direction: "up", value: "Annual projection" }}
            />
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Assumptions */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl">
          <button
            onClick={() => setShowAssumptions(!showAssumptions)}
            className="flex w-full items-center justify-between rounded-lg border bg-card p-4 text-left transition-colors hover:bg-accent"
          >
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">{t("roiCalculator.assumptions")}</span>
            </div>
            {showAssumptions ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>

          <AnimatePresence>
            {showAssumptions && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <Card className="mt-2">
                  <CardContent className="p-6">
                    <ul className="space-y-3 text-sm text-muted-foreground">
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.fuelSavingsLabel")}</span>
                        <span>{t("roiCalculator.fuelSavingsDesc")}</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.tollSavingsLabel")}</span>
                        <span>{t("roiCalculator.tollSavingsDesc")}</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.timeSavingsLabel")}</span>
                        <span>{t("roiCalculator.timeSavingsDesc")}</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.adminSavingsLabel")}</span>
                        <span>{t("roiCalculator.adminSavingsDesc")}</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.invoiceSavingsLabel")}</span>
                        <span>{t("roiCalculator.invoiceSavingsDesc")}</span>
                      </li>
                      <li className="flex gap-2">
                        <span className="font-medium text-foreground shrink-0">{t("roiCalculator.disclaimerLabel")}</span>
                        <span>{t("roiCalculator.disclaimerDesc")}</span>
                      </li>
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </SectionWrapper>

      {/* Powered by Operion ERP */}
      <SectionWrapper className="border-t bg-muted/30">
        <div className="mx-auto max-w-2xl text-center py-16">
          <h2 className="text-2xl font-bold tracking-tight">{t("roiCalculator.poweredBy")}</h2>
          <p className="mt-4 text-muted-foreground leading-relaxed">
            {t("roiCalculator.poweredByDesc")}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <a
              href="/waitlist"
              onClick={() => trackCTAClick("roi_calculator", "/roi-calculator")}
              className="inline-flex items-center rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              {t("roiCalculator.joinWaitlist")}
            </a>
            <a
              href="/features"
              className="inline-flex items-center rounded-lg border px-6 py-3 text-sm font-medium hover:bg-accent transition-colors"
            >
              {t("roiCalculator.exploreFeatures")}
            </a>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
