import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Link } from "react-router"
import { LifeBuoy, Bug, Lightbulb, Mail, Phone, MapPin, Clock, MessageSquare, BookOpen, ChevronDown, ChevronUp, Filter, Headphones, Bot, AlertCircle } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label, Textarea } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useCreateTicket, useTickets, useTutorials } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { SupportModal } from "@/components/shared/support-modal"
import { LiveChat } from "@/components/shared/live-chat"


const bugSchema = z.object({
  title: z.string().min(5, "Title must be at least 5 characters"),
  description: z.string().min(20, "Please provide a detailed description"),
  steps: z.string().optional(),
})

const featureSchema = z.object({
  title: z.string().min(5, "Title must be at least 5 characters"),
  description: z.string().min(20, "Please describe the feature you'd like"),
  use_case: z.string().optional(),
})

type BugForm = z.infer<typeof bugSchema>
type FeatureForm = z.infer<typeof featureSchema>

const faqKeys = [
  { q: "support.faq1q", a: "support.faq1a" },
  { q: "support.faq2q", a: "support.faq2a" },
  { q: "support.faq3q", a: "support.faq3a" },
  { q: "support.faq4q", a: "support.faq4a" },
]

const statusFilterOptions = ["all", "open", "in_progress", "resolved", "closed"] as const

export default function SupportPage() {
  const { t } = useLocale()
  const createTicket = useCreateTicket()
  const { data: ticketsData, isLoading: ticketsLoading, isError } = useTickets()
  const {
    data: tutorialsData,
    isLoading: tutorialsLoading,
    isError: tutorialsError,
    refetch: tutorialsRefetch,
  } = useTutorials()
  const tutorials = tutorialsData ?? []
  const bugForm = useForm<BugForm>({ resolver: zodResolver(bugSchema) })
  const featureForm = useForm<FeatureForm>({ resolver: zodResolver(featureSchema) })

  const [expandedSolution, setExpandedSolution] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [supportModalOpen, setSupportModalOpen] = useState(false)

  function onBugSubmit(data: BugForm) {
    createTicket.mutate({
      subject: `[Bug] ${data.title}`,
      description: data.steps
        ? `${data.description}\n\nSteps to reproduce:\n${data.steps}`
        : data.description,
    })
    bugForm.reset()
  }

  function onFeatureSubmit(data: FeatureForm) {
    createTicket.mutate({
      subject: `[Feature] ${data.title}`,
      description: data.use_case
        ? `${data.description}\n\nUse case:\n${data.use_case}`
        : data.description,
    })
    featureForm.reset()
  }

  const allTickets = ticketsData ?? []
  const filteredTickets = statusFilter === "all" ? allTickets : allTickets.filter((t) => t.status === statusFilter)

  const priorityBadge = (priority: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      low: "secondary",
      medium: "default",
      high: "destructive",
      urgent: "destructive",
    }
    return <Badge variant={variants[priority] || "default"}>{priority}</Badge>
  }

  const statusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      open: "default",
      in_progress: "secondary",
      resolved: "success",
      closed: "outline",
    }
    return <Badge variant={variants[status] || "default"}>{status.replace("_", " ")}</Badge>
  }

  return (
    <>
      <Helmet><title>{t("support.pageTitle")}</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("support.heading")}</h1>
          <p className="mt-2 text-muted-foreground">{t("support.description")}</p>
        </motion.div>

        <Tabs defaultValue="submit" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="submit">{t("support.submitTicket")}</TabsTrigger>
            <TabsTrigger value="tickets">{t("support.myTickets")}</TabsTrigger>
            <TabsTrigger value="knowledge">{t("support.knowledgeBase")}</TabsTrigger>
            <TabsTrigger value="chat">
              <Bot className="mr-1.5 h-4 w-4" />
              {t("support.chat.title")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="submit" className="space-y-8">
            <div className="grid gap-8 lg:grid-cols-2">
              {/* Bug Report */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bug className="h-5 w-5" /> {t("support.reportBug")}</CardTitle>
                    <CardDescription>{t("support.reportBugDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={bugForm.handleSubmit(onBugSubmit)} className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="bug-title">{t("support.bugTitle")}</Label>
                        <Input id="bug-title" placeholder={t("support.bugTitlePlaceholder")} {...bugForm.register("title")} />
                        {bugForm.formState.errors.title && <p className="text-xs text-destructive">{bugForm.formState.errors.title.message}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="bug-desc">{t("support.bugDesc")}</Label>
                        <Textarea id="bug-desc" rows={4} placeholder={t("support.bugDescPlaceholder")} {...bugForm.register("description")} />
                        {bugForm.formState.errors.description && <p className="text-xs text-destructive">{bugForm.formState.errors.description.message}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="bug-steps">{t("support.bugSteps")} <span className="text-muted-foreground">(optional)</span></Label>
                        <Textarea id="bug-steps" rows={3} placeholder={t("support.bugStepsPlaceholder")} {...bugForm.register("steps")} />
                      </div>
                      <Button type="submit" disabled={createTicket.isPending} className="w-full">
                        {createTicket.isPending ? t("support.submitting") : t("support.submitBug")}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Feature Request */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Lightbulb className="h-5 w-5" /> {t("support.requestFeature")}</CardTitle>
                    <CardDescription>{t("support.requestFeatureDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={featureForm.handleSubmit(onFeatureSubmit)} className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="feature-title">{t("support.featureTitle")}</Label>
                        <Input id="feature-title" placeholder={t("support.featureTitlePlaceholder")} {...featureForm.register("title")} />
                        {featureForm.formState.errors.title && <p className="text-xs text-destructive">{featureForm.formState.errors.title.message}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="feature-desc">{t("support.featureDesc")}</Label>
                        <Textarea id="feature-desc" rows={4} placeholder={t("support.featureDescPlaceholder")} {...featureForm.register("description")} />
                        {featureForm.formState.errors.description && <p className="text-xs text-destructive">{featureForm.formState.errors.description.message}</p>}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="feature-use-case">{t("support.featureUseCase")} <span className="text-muted-foreground">(optional)</span></Label>
                        <Textarea id="feature-use-case" rows={2} placeholder={t("support.featureUseCasePlaceholder")} {...featureForm.register("use_case")} />
                      </div>
                      <Button type="submit" disabled={createTicket.isPending} className="w-full">
                        {createTicket.isPending ? t("support.submitting") : t("support.submitFeature")}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Contact Info */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><LifeBuoy className="h-5 w-5" /> {t("support.contactInfo")}</CardTitle>
                  <CardDescription>{t("support.contactInfoDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-4">
                    {[
                      { icon: Mail, label: t("support.email"), value: "support@operionerp.xyz" },
                      { icon: Phone, label: t("support.phone"), value: "+40 123 456 789" },
                      { icon: MapPin, label: t("support.office"), value: "Bucharest, Romania" },
                      { icon: Clock, label: t("support.hours"), value: "Mon–Fri, 9–18 EET" },
                    ].map((c) => (
                      <div key={c.label} className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                          <c.icon className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">{c.label}</p>
                          <p className="text-sm font-medium">{c.value}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Live Chat */}
            <div className="grid gap-8 lg:grid-cols-2">
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Headphones className="h-5 w-5" /> {t("support.liveChat")}</CardTitle>
                    <CardDescription>{t("support.liveChatDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button className="w-full" onClick={() => setSupportModalOpen(true)}>
                      <MessageSquare className="mr-2 h-4 w-4" />
                      {t("support.startChat")}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bot className="h-5 w-5" /> {t("support.chat.title")}</CardTitle>
                    <CardDescription>{t("support.aiAssistantDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      {t("support.chat.welcome")}
                    </p>
                    <div className="flex items-center gap-2">
                      <Badge variant="success" className="text-xs">{t("support.online")}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {t("support.liveChatDesc")} Use the <strong>{t("support.aiChat")}</strong> tab above or the chat bubble at the bottom-right to start talking with ARGO.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="tickets" className="space-y-8">
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2"><MessageSquare className="h-5 w-5" /> {t("support.ticketHistory")}</CardTitle>
                      <CardDescription>{t("support.ticketHistoryDesc")}</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Filter className="h-4 w-4 text-muted-foreground" />
                      <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {statusFilterOptions.map((s) => (
                          <option key={s} value={s}>{s === "all" ? t("support.allStatuses") : s.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {ticketsLoading ? (
                    <div className="flex justify-center py-12">
                      <LoadingSpinner size="lg" />
                    </div>
                  ) : isError ? (
                    <EmptyState
                      icon={<AlertCircle className="h-12 w-12" />}
                      title={t("support.failedToLoadTickets")}
                      description={t("support.failedToLoadTicketsDesc")}
                    />
                  ) : allTickets.length === 0 ? (
                    <EmptyState title={t("support.noTickets")} description={t("support.noTicketsDesc")} />
                  ) : filteredTickets.length === 0 ? (
                    <EmptyState title={t("dashboard.noTicketsFound")} description={t("dashboard.noTicketsFilter")} />
                  ) : (
                    <div className="space-y-3">
                      {filteredTickets.map((ticket) => (
                        <div key={ticket.id} className="flex items-center justify-between rounded-lg border p-4">
                          <div className="flex items-center gap-4">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                              <MessageSquare className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{ticket.subject}</p>
                              <p className="text-xs text-muted-foreground">
                                {t("support.createdUpdated")
                                  .replace("{created}", new Date(ticket.created_at).toLocaleDateString())
                                  .replace("{updated}", new Date(ticket.updated_at).toLocaleDateString())}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {priorityBadge(ticket.priority)}
                            {statusBadge(ticket.status)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="knowledge" className="space-y-8">
            {/* Knowledge Base */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
              <h2 className="text-xl font-bold tracking-tight mb-2">{t("support.knowledgeBase")}</h2>
              <p className="text-sm text-muted-foreground mb-6">{t("support.knowledgeBaseDesc")}</p>

              {tutorialsLoading ? (
                <div className="flex justify-center py-12">
                  <LoadingSpinner size="lg" />
                </div>
              ) : tutorialsError ? (
                <EmptyState
                  icon={<AlertCircle className="h-12 w-12 text-destructive/70" />}
                  title={t("support.kbError")}
                  description={t("support.kbErrorDesc")}
                  action={
                    <Button variant="outline" onClick={() => tutorialsRefetch()}>
                      {t("support.kbRetry")}
                    </Button>
                  }
                />
              ) : tutorials.length === 0 ? (
                <EmptyState
                  icon={<BookOpen className="h-12 w-12 text-muted-foreground/50" />}
                  title={t("support.kbEmpty")}
                  description={t("support.kbEmptyDesc")}
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {tutorials.map((tutorial) => (
                    <Link key={tutorial.slug} to={`/tutorials/${tutorial.slug}`} className="h-full">
                      <Card className="h-full transition-shadow hover:shadow-md">
                        <CardContent className="flex h-full flex-col items-start gap-2 p-5">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                            <BookOpen className="h-5 w-5 text-primary" />
                          </div>
                          <p className="mt-1 font-medium text-sm leading-snug">{tutorial.title}</p>
                          <p className="line-clamp-2 text-xs text-muted-foreground">{tutorial.excerpt}</p>
                          <span className="mt-auto flex items-center gap-1 pt-2 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            {tutorial.reading_time_minutes} min read
                          </span>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </motion.div>

            {/* Common Solutions */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
              <h2 className="text-xl font-bold tracking-tight mb-4">{t("support.faqDesc")}</h2>
              <Card>
                <CardContent className="p-0">
                  <div className="divide-y">
                    {faqKeys.map((item, i) => (
                      <div key={i} className="p-4">
                        <button
                          onClick={() => setExpandedSolution(expandedSolution === i ? null : i)}
                          className="flex w-full items-center justify-between text-left"
                        >
                          <span className="text-sm font-medium">{t(item.q)}</span>
                          {expandedSolution === i ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                        {expandedSolution === i && (
                          <motion.p
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            className="mt-2 text-sm text-muted-foreground"
                          >
                            {t(item.a)}
                          </motion.p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="chat" className="space-y-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="h-[600px]"
            >
              <LiveChat variant="embedded" />
            </motion.div>
          </TabsContent>
        </Tabs>
        <SupportModal open={supportModalOpen} onOpenChange={setSupportModalOpen} />

        {/* Floating chat widget */}
        <div className="fixed bottom-6 right-6 z-50">
          <LiveChat variant="floating" />
        </div>
      </SectionWrapper>
    </>
  )
}
