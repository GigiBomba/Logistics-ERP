import { useState } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Code2, Send, RotateCcw, ShieldAlert, Terminal, Clock } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

// ─── Curated public endpoints (subset of the real public API surface) ───

interface DemoEndpoint {
  id: string
  method: "GET" | "POST"
  path: string
  label: string
  bodyTemplate?: string
}

const demoEndpoints: DemoEndpoint[] = [
  { id: "blog-posts", method: "GET", path: "/api/v1/blog/posts", label: "List blog posts" },
  { id: "tutorials", method: "GET", path: "/api/v1/tutorials", label: "List tutorials" },
  { id: "changelog", method: "GET", path: "/api/v1/changelog", label: "Changelog entries" },
  { id: "roadmap", method: "GET", path: "/api/v1/roadmap", label: "Roadmap items" },
  { id: "status", method: "GET", path: "/api/v1/status", label: "Service status" },
  { id: "announcements", method: "GET", path: "/api/v1/announcements", label: "Announcements" },
  { id: "downloads-latest", method: "GET", path: "/api/v1/downloads/latest", label: "Latest desktop release" },
  { id: "waitlist-count", method: "GET", path: "/api/v1/waitlist/count", label: "Waitlist signup count" },
  {
    id: "waitlist-join",
    method: "POST",
    path: "/api/v1/waitlist",
    label: "Join the waitlist",
    bodyTemplate: '{\n  "email": "dispatcher@example.com",\n  "company_name": "Example Carrier",\n  "role": "fleet_manager"\n}',
  },
  {
    id: "newsletter",
    method: "POST",
    path: "/api/v1/newsletter/subscribe",
    label: "Subscribe to newsletter",
    bodyTemplate: '{\n  "email": "ops@example.com"\n}',
  },
]

// ─── Local sandbox execution (no network calls) ─────────────────────────

interface DemoResponse {
  status: number
  statusText: string
  latencyMs: number
  data: unknown
}

// Simple rolling-window rate limiter so the demo behaves like a real API.
const DEMO_LIMIT = 5
const DEMO_WINDOW_MS = 30_000
let demoTimestamps: number[] = []

function cannedBody(endpoint: DemoEndpoint, bodyText: string): unknown {
  let submitted: Record<string, unknown> = {}
  if (bodyText.trim()) {
    try {
      submitted = JSON.parse(bodyText)
    } catch {
      submitted = {}
    }
  }
  switch (endpoint.id) {
    case "blog-posts":
      return {
        items: [
          {
            id: 1,
            title: "Operion AI Co-Pilot: Intelligent Automation for Modern Logistics",
            slug: "operion-ai-copilot-intelligent-logistics-automation",
            category: "AI & Automation",
            tags: ["ai-copilot", "logistics-automation"],
            reading_time_minutes: 6,
          },
          {
            id: 2,
            title: "Trip Profitability: How to Calculate Profit Per Transport Job",
            slug: "how-to-calculate-trip-profitability-road-transport",
            category: "Profitability & Transport Finance",
            tags: ["trip-profitability", "margin-analysis"],
            reading_time_minutes: 8,
          },
        ],
        total: 2,
        page: 1,
        page_size: 20,
      }
    case "tutorials":
      return [
        {
          id: "t-1",
          title: "Your First Route Plan",
          slug: "your-first-route-plan",
          category: "beginner",
          excerpt: "Plan your first multi-stop route in under five minutes.",
          reading_time_minutes: 7,
        },
        {
          id: "t-2",
          title: "Dispatching Jobs to Drivers",
          slug: "dispatching-jobs-to-drivers",
          category: "dispatcher",
          excerpt: "Dispatch a load to a driver with automated checks.",
          reading_time_minutes: 6,
        },
      ]
    case "changelog":
      return [
        {
          version: "0.9.0",
          release_date: "2026-07-20",
          sections: [
            { type: "added", items: ["AI Co-Pilot voice mode", "Bulk CMR generation"] },
            { type: "changed", items: ["Faster route recalculation"] },
          ],
        },
      ]
    case "roadmap":
      return [
        {
          id: "r-1",
          title: "Mobile driver app",
          description: "Native driver app for job confirmation and proof of delivery.",
          status: "in_progress",
          category: "Mobile",
        },
        {
          id: "r-2",
          title: "TIMOCOM exchange connector",
          description: "Two-way load board integration.",
          status: "planned",
          category: "Integrations",
        },
      ]
    case "status":
      return [
        {
          name: "Core Platform",
          services: [
            { name: "API Backend", status: "operational", updated_at: "2026-08-02T08:00:00Z" },
            { name: "Desktop App", status: "operational", updated_at: "2026-08-02T08:00:00Z" },
          ],
        },
      ]
    case "announcements":
      return [
        {
          id: "a-1",
          title: "Operion 0.9 public beta is open",
          published_at: "2026-07-20T10:00:00Z",
        },
      ]
    case "downloads-latest":
      return { version: "Pre-release", platform: "Windows 10/11 (64-bit)", url: "https://operionerp.xyz/download" }
    case "waitlist-count":
      return { count: 482, status: "active" }
    case "waitlist-join":
      return {
        id: 1042,
        email: (submitted.email as string) ?? "—",
        status: "joined",
        message: "You're on the waitlist — we'll email you when early access opens.",
      }
    case "newsletter":
      return { ok: true, message: "Subscription confirmed. Check your inbox." }
    default:
      return { detail: "Unknown demo endpoint." }
  }
}

function runDemoRequest(endpoint: DemoEndpoint, bodyText: string): Promise<DemoResponse> {
  const now = Date.now()
  demoTimestamps = demoTimestamps.filter((t) => now - t < DEMO_WINDOW_MS)

  if (demoTimestamps.length >= DEMO_LIMIT) {
    const retryAfter = Math.max(1, Math.ceil((DEMO_WINDOW_MS - (now - demoTimestamps[0])) / 1000))
    return Promise.resolve({
      status: 429,
      statusText: "Too Many Requests",
      latencyMs: 15,
      data: { detail: "Rate limit exceeded — sandbox allows 5 requests per 30 seconds.", retry_after_seconds: retryAfter },
    })
  }

  demoTimestamps.push(now)
  const latencyMs = 250 + Math.floor(Math.random() * 450)
  const isPost = endpoint.method === "POST"
  const status = isPost ? 201 : 200
  const statusText = isPost ? "Created" : "OK"
  const data = cannedBody(endpoint, bodyText)

  return new Promise<DemoResponse>((resolve) => {
    setTimeout(() => resolve({ status, statusText, latencyMs, data }), latencyMs)
  })
}

export default function ApiPlaygroundPage() {
  const { t } = useLocale()
  const [endpoint, setEndpoint] = useState<DemoEndpoint>(demoEndpoints[0])
  const [bodyText, setBodyText] = useState(demoEndpoints[0].bodyTemplate ?? "")
  const [response, setResponse] = useState<DemoResponse | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  function selectEndpoint(id: string) {
    const next = demoEndpoints.find((e) => e.id === id) ?? demoEndpoints[0]
    setEndpoint(next)
    setBodyText(next.bodyTemplate ?? "")
    setResponse(null)
  }

  async function handleSend() {
    setIsRunning(true)
    const result = await runDemoRequest(endpoint, bodyText)
    setResponse(result)
    setIsRunning(false)
  }

  function handleReset() {
    setResponse(null)
    setIsRunning(false)
  }

  const methodColor = endpoint.method === "GET"
    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
    : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"

  return (
    <>
      <SeoHead
        title="API Playground — Operion"
        description="Try the Operion public API in a sandboxed demo. No live requests are made — requests run against canned responses with realistic latency and rate limiting."
        canonical="https://operionerp.xyz/api-playground"
      />

      <HeroSection
        title="API Playground"
        description="Explore the Operion public API with an interactive, sandboxed demo. Every request is simulated locally — no real API calls are made."
        align="center"
        size="large"
      />

      <SectionWrapper className="pt-0">
        <div className="mx-auto max-w-3xl space-y-6">
          {/* Sandbox framing */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div>
                <p className="text-sm font-semibold">{t("apiPlayground.sandboxNote")}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {t("apiPlayground.sandboxNoteDesc")}
                </p>
              </div>
            </div>
          </motion.div>

          {/* Request builder */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card>
              <CardContent className="space-y-5 p-6">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{t("apiPlayground.endpoint")}</Label>
                    <select
                      value={endpoint.id}
                      onChange={(e) => selectEndpoint(e.target.value)}
                      className="h-10 w-full rounded-md border border-input bg-transparent px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      {demoEndpoints.map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.method} {e.path}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t("apiPlayground.method")}</Label>
                    <div className="flex h-10 items-center rounded-md border border-input px-3">
                      <Badge className={`font-mono text-xs ${methodColor}`}>{endpoint.method}</Badge>
                      <span className="ml-2 truncate font-mono text-sm text-muted-foreground">
                        {endpoint.path}
                      </span>
                    </div>
                  </div>
                </div>

                {endpoint.method === "POST" && (
                  <div className="space-y-2">
                    <Label>{t("apiPlayground.body")}</Label>
                    <textarea
                      value={bodyText}
                      onChange={(e) => setBodyText(e.target.value)}
                      rows={5}
                      spellCheck={false}
                      className="w-full rounded-md border border-input bg-muted/30 p-3 font-mono text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    />
                  </div>
                )}

                <div className="flex items-center gap-3">
                  <Button onClick={handleSend} disabled={isRunning}>
                    {isRunning ? t("apiPlayground.sending") : t("apiPlayground.send")}
                    <Send className="ml-2 h-4 w-4" />
                  </Button>
                  <Button variant="ghost" onClick={handleReset} disabled={!response && !isRunning}>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    {t("apiPlayground.reset")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Response viewer */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card>
              <CardContent className="space-y-4 p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-5 w-5 text-primary" />
                    <h2 className="font-semibold">{t("apiPlayground.response")}</h2>
                  </div>
                  {response && (
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge
                        variant={
                          response.status >= 400 ? "destructive" : response.status >= 300 ? "secondary" : "success"
                        }
                        className="font-mono"
                      >
                        {response.status} {response.statusText}
                      </Badge>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {response.latencyMs} ms
                      </span>
                    </div>
                  )}
                </div>

                {response ? (
                  <pre className="max-h-96 overflow-auto rounded-lg bg-muted/40 p-4 font-mono text-xs leading-relaxed">
                    {JSON.stringify(response.data, null, 2)}
                  </pre>
                ) : (
                  <div className="rounded-lg border border-dashed p-8 text-center">
                    <Code2 className="mx-auto h-8 w-8 text-muted-foreground/40" />
                    <p className="mt-3 text-sm text-muted-foreground">
                      {t("apiPlayground.noResponse")}
                    </p>
                  </div>
                )}

                <p className="text-xs text-muted-foreground">
                  {t("apiPlayground.rateLimitNote")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
