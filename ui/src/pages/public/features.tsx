import { Helmet } from "react-helmet-async"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { motion } from "motion/react"
import {
  Route,
  MapPin,
  Navigation,
  Satellite,
  Wrench,
  Map,
  Radio,
  ClipboardCheck,
  RefreshCw,
  Scan,
  Archive,
  FileText,
  BarChart3,
  TrendingUp,
  Download,
  UserCheck,
  Award,
  Calendar,
} from "lucide-react"

const categories = [
  {
    title: "Route Planning & Optimization",
    features: [
      {
        icon: Route,
        title: "Intelligent Route Planning",
        description:
          "Advanced algorithms optimize for time, distance, and fuel efficiency, ensuring every trip is as cost-effective as possible.",
      },
      {
        icon: MapPin,
        title: "Multi-Stop Optimization",
        description:
          "Plan complex multi-stop routes in seconds. Our engine evaluates hundreds of permutations to find the most efficient sequence.",
      },
      {
        icon: Navigation,
        title: "Real-Time Traffic Integration",
        description:
          "Routes adjust dynamically based on live traffic conditions, helping drivers avoid delays and reach destinations faster.",
      },
    ],
  },
  {
    title: "Fleet Management",
    features: [
      {
        icon: Satellite,
        title: "Real-Time GPS Tracking",
        description:
          "Monitor every vehicle's location and status instantly on an interactive map with live position updates every few seconds.",
      },
      {
        icon: Wrench,
        title: "Vehicle Maintenance Tracking",
        description:
          "Schedule and track maintenance to minimize downtime. Get reminders for inspections, oil changes, and tyre rotations.",
      },
      {
        icon: Map,
        title: "Geofencing & Alerts",
        description:
          "Set geographic boundaries and receive instant notifications when vehicles enter or leave designated areas.",
      },
    ],
  },
  {
    title: "Dispatch & Operations",
    features: [
      {
        icon: Radio,
        title: "Automated Job Assignment",
        description:
          "Match jobs to the best available drivers automatically based on location, skills, vehicle capacity, and current workload.",
      },
      {
        icon: ClipboardCheck,
        title: "Digital Proof of Delivery",
        description:
          "Capture signatures, photos, and timestamps on delivery with a mobile-friendly interface that works even offline.",
      },
      {
        icon: RefreshCw,
        title: "Real-Time Status Updates",
        description:
          "Track every job from assignment to completion. Dispatchers and customers get live updates at every stage.",
      },
    ],
  },
  {
    title: "Document Management",
    features: [
      {
        icon: Scan,
        title: "AI-Powered OCR",
        description:
          "Scan and digitize invoices, CMRs, and receipts automatically. Our OCR engine extracts key fields with high accuracy.",
      },
      {
        icon: Archive,
        title: "Digital Archive",
        description:
          "Store and search all documents in a secure cloud repository. Advanced filters make finding any document quick and effortless.",
      },
      {
        icon: FileText,
        title: "Automated Invoicing",
        description:
          "Generate invoices from delivery data automatically. Customize templates and send them directly to clients from the platform.",
      },
    ],
  },
  {
    title: "Analytics & Reporting",
    features: [
      {
        icon: BarChart3,
        title: "Custom Dashboards",
        description:
          "Build personalized views of the metrics that matter most. Drag, drop, and configure widgets to match your workflow.",
      },
      {
        icon: TrendingUp,
        title: "KPI Tracking",
        description:
          "Monitor key performance indicators across your entire operation, from fuel consumption to on-time delivery rates.",
      },
      {
        icon: Download,
        title: "Export & Integration",
        description:
          "Export reports in multiple formats and integrate with your existing tools through our open API and native connectors.",
      },
    ],
  },
  {
    title: "Driver Management",
    features: [
      {
        icon: UserCheck,
        title: "Driver Profiles",
        description:
          "Complete driver database with certifications, licenses, medical cards, and training documents stored in one central location.",
      },
      {
        icon: Award,
        title: "Performance Tracking",
        description:
          "Monitor driver efficiency, safety scores, and on-time delivery rates. Identify top performers and areas for improvement.",
      },
      {
        icon: Calendar,
        title: "Schedule Management",
        description:
          "Plan driver shifts and manage availability with an intuitive calendar. Reduce scheduling conflicts and ensure coverage.",
      },
    ],
  },
]

export default function FeaturesPage() {
  return (
    <div className="flex flex-col">
      <Helmet>
        <title>Features - Operion ERP</title>
      </Helmet>

      {/* Header */}
      <SectionWrapper>
        <PageHeader
          title="Powerful Features for Modern Logistics"
          description="Everything you need to run your fleet operations efficiently, from route planning to analytics."
          className="text-center"
        />
      </SectionWrapper>

      {/* Feature Categories */}
      {categories.map((category, categoryIndex) => (
        <SectionWrapper
          key={category.title}
          className={categoryIndex % 2 === 1 ? "bg-muted/30" : undefined}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{
              duration: 0.5,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              {category.title}
            </h2>
          </motion.div>
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {category.features.map((feature, featureIndex) => (
              <FeatureCard
                key={feature.title}
                icon={feature.icon}
                title={feature.title}
                description={feature.description}
                index={featureIndex}
              />
            ))}
          </div>
        </SectionWrapper>
      ))}
    </div>
  )
}
