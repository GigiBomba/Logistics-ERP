import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Sparkles,
  Lightbulb,
  LifeBuoy,
  Zap,
  Route,
  FileText,
  ExternalLink,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import type { OnboardingStep } from "@/types"

const onboardingSteps: OnboardingStep[] = [
  {
    id: "verify-email",
    title: "Verify your email",
    description: "Confirm your email address to secure your account and receive important notifications.",
    completed: true,
    required: true,
    link: "/dashboard/profile",
  },
  {
    id: "company-profile",
    title: "Set up company profile",
    description: "Add your company details, logo, and branding to personalize your Operion workspace.",
    completed: false,
    required: true,
    link: "/dashboard/company",
  },
  {
    id: "choose-plan",
    title: "Choose your plan",
    description: "Select the subscription tier that fits your fleet size and feature requirements.",
    completed: false,
    required: true,
    link: "/dashboard/subscription",
  },
  {
    id: "download-desktop",
    title: "Download Operion Desktop",
    description: "Install the desktop application for Windows, macOS, or Linux to get started.",
    completed: false,
    required: false,
    link: "/dashboard/downloads",
  },
  {
    id: "first-route",
    title: "Create your first route",
    description: "Build and optimize your first delivery route using the route planner.",
    completed: false,
    required: false,
    link: "/docs/getting-started/quick-start",
  },
  {
    id: "add-team",
    title: "Add team members",
    description: "Invite dispatchers, drivers, and administrators to collaborate in your workspace.",
    completed: false,
    required: false,
    link: "/dashboard/organizations",
  },
  {
    id: "notifications",
    title: "Set up notifications",
    description: "Configure email and in-app alerts for deliveries, delays, and system events.",
    completed: false,
    required: false,
    link: "/dashboard/settings",
  },
  {
    id: "explore-docs",
    title: "Explore documentation",
    description: "Browse guides, API references, and tutorials to unlock the full power of Operion.",
    completed: false,
    required: false,
    link: "/docs",
  },
]

const tutorials = [
  {
    title: "Route Optimization 101",
    description: "Learn how to build efficient multi-stop routes in under 5 minutes.",
    icon: Route,
    level: "Beginner",
    duration: "5 min",
  },
  {
    title: "Dispatch Console Basics",
    description: "Master real-time dispatching, driver assignments, and live tracking.",
    icon: Zap,
    level: "Intermediate",
    duration: "8 min",
  },
  {
    title: "Fleet Analytics Overview",
    description: "Understand delivery metrics, fuel efficiency, and driver performance reports.",
    icon: FileText,
    level: "Advanced",
    duration: "12 min",
  },
  {
    title: "API Integration Guide",
    description: "Connect Operion with your existing ERP, WMS, or TMS systems.",
    icon: ExternalLink,
    level: "Developer",
    duration: "15 min",
  },
]

const releases = [
  {
    version: "1.2.0",
    date: "July 2026",
    title: "Fleet Analytics Dashboard",
    description: "New analytics views for fuel efficiency, driver scores, and delivery success rates.",
  },
  {
    version: "1.1.0",
    date: "June 2026",
    title: "Multi-warehouse Support",
    description: "Manage inventory and routes across multiple warehouses and distribution centers.",
  },
  {
    version: "1.0.0",
    date: "May 2026",
    title: "Operion GA Release",
    description: "General availability with route optimization, dispatch console, and mobile apps.",
  },
]

const bestPractices = [
  "Start with a small pilot fleet before rolling out to your entire operation.",
  "Set up geofences and automated alerts to reduce manual monitoring overhead.",
  "Regularly review route analytics to identify recurring inefficiencies.",
  "Keep driver mobile apps updated to ensure access to the latest navigation data.",
  "Use API webhooks to sync delivery events with your CRM or support tools.",
]

function CircularProgress({ value, total }: { value: number; total: number }) {
  const percentage = Math.round((value / total) * 100)
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="flex items-center gap-4">
      <div className="relative flex h-24 w-24 shrink-0 items-center justify-center">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            className="text-muted/30"
          />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeLinecap="round"
            className="text-primary"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold">{percentage}%</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-medium">
          {value} of {total} steps completed
        </p>
        <p className="text-xs text-muted-foreground">
          Finish the required steps to get the most out of Operion.
        </p>
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  const completedCount = onboardingSteps.filter((s) => s.completed).length
  const totalCount = onboardingSteps.length
  const requiredSteps = onboardingSteps.filter((s) => s.required)
  const requiredCompleted = requiredSteps.filter((s) => s.completed).length

  return (
    <>
      <Helmet>
        <title>Getting Started — Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h1 className="text-3xl font-bold tracking-tight">Getting Started</h1>
          <p className="mt-2 text-muted-foreground">
            Complete these steps to set up your Operion account
          </p>
        </motion.div>

        {/* Overall Progress */}
        <motion.div
          className="mt-8"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardContent className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center">
              <CircularProgress value={completedCount} total={totalCount} />
              <div className="flex-1 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Required steps</span>
                  <span className="font-medium">
                    {requiredCompleted} / {requiredSteps.length} completed
                  </span>
                </div>
                <Progress value={(requiredCompleted / requiredSteps.length) * 100} variant="success" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">All steps</span>
                  <span className="font-medium">
                    {completedCount} / {totalCount} completed
                  </span>
                </div>
                <Progress value={(completedCount / totalCount) * 100} />
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Checklist */}
        <div className="mt-10 space-y-4">
          <h2 className="text-xl font-bold tracking-tight">Onboarding Checklist</h2>
          {onboardingSteps.map((step, index) => (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.05 * index, ease: [0.22, 1, 0.36, 1] }}
              >
                <Card
                  className={`transition-colors ${step.completed ? "border-green-200/50 bg-green-50/30 dark:border-green-900/30 dark:bg-green-950/20" : ""}`}
                >
                  <CardContent className="flex items-start gap-4 p-5">
                    <div className="mt-0.5 shrink-0">
                      {step.completed ? (
                        <CheckCircle2 className="h-6 w-6 text-green-600" />
                      ) : (
                        <Circle className="h-6 w-6 text-muted-foreground/40" />
                      )}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-muted-foreground">
                          Step {index + 1}
                        </span>
                        {step.required && (
                          <Badge variant="destructive" className="text-[10px]">
                            Required
                          </Badge>
                        )}
                      </div>
                      <h3
                        className={`text-sm font-semibold ${step.completed ? "line-through opacity-60" : ""}`}
                      >
                        {step.title}
                      </h3>
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    </div>
                    <div className="shrink-0">
                      {step.completed ? (
                        <Badge variant="success">Done</Badge>
                      ) : (
                        <Button size="sm" asChild>
                          <Link to={step.link || "#"}>
                            Complete <ArrowRight className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))
          }
        </div>

        {/* Recommended Tutorials */}
        <motion.div
          className="mt-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">Recommended Tutorials</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {tutorials.map((tutorial, index) => (
              <motion.div
                key={tutorial.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.05 * index }}
              >
                <Card className="h-full transition-shadow hover:shadow-md">
                  <CardContent className="flex flex-col gap-4 p-5">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <tutorial.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold">{tutorial.title}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">{tutorial.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-[10px]">
                        {tutorial.level}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{tutorial.duration}</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Release Highlights + Best Practices */}
        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-4">Release Highlights</h2>
            <div className="space-y-4">
              {releases.map((release, index) => (
                <motion.div
                  key={release.version}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.05 * index }}
                >
                  <Card>
                    <CardContent className="p-5">
                      <div className="flex items-start gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                          <Sparkles className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold">{release.title}</h3>
                            <Badge variant="outline" className="text-[10px]">
                              v{release.version}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">{release.description}</p>
                          <p className="mt-2 text-xs text-muted-foreground/60">{release.date}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-4">Best Practices</h2>
            <Card>
              <CardContent className="p-5">
                <ul className="space-y-3">
                  {bestPractices.map((practice, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-muted-foreground">
                      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                      {practice}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* CTA */}
        <motion.div
          className="mt-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <Callout variant="info" icon={<LifeBuoy className="h-5 w-5 shrink-0 mt-0.5" />}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold">Need help?</p>
                <p className="text-sm">
                  Our support team is available to assist with onboarding, configuration, and troubleshooting.
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/dashboard/support">Contact Support</Link>
              </Button>
            </div>
          </Callout>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
