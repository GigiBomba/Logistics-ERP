import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Mail, Phone, BookOpen, MessageCircle, ArrowRight } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input, Label, Textarea } from "@/components/ui/input"
import { JsonLd, contactPageSchema } from "@/components/seo/structured-data"

const contactSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email"),
  subject: z.string().min(5, "Subject must be at least 5 characters"),
  message: z.string().min(10, "Message must be at least 10 characters"),
})

type ContactForm = z.infer<typeof contactSchema>

export default function ContactPage() {
  const { t } = useLocale()

  const contactInfo = [
    { icon: Mail, label: t("contact.emailLabel"), value: "contact@operionerp.xyz" },
    { icon: Phone, label: t("contact.phoneLabel"), value: "+40 123 456 789" },
  ]

  const contactMethods = [
    { icon: Mail, title: t("contact.emailSupport"), description: t("contact.emailSupportDesc"), detail: "contact@operionerp.xyz", badge: t("contact.bestWay") },
    { icon: Phone, title: t("contact.phoneSupport"), description: t("contact.phoneSupportDesc"), detail: "+40 123 456 789", badge: t("contact.inquireDetails") },
  ]

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ContactForm>({
    resolver: zodResolver(contactSchema),
  })

  function onSubmit(_data: ContactForm) {
    // TODO: Implement backend endpoint - currently showing success toast
    toast.success(t("contact.successMessage"))
    reset()
  }

  return (
    <>
      <Helmet>
        <title>{t("contact.meta.title")}</title>
        <meta name="description" content={t("contact.meta.description")} />
        <link rel="canonical" href="https://operion.com/contact" />
      </Helmet>
      <JsonLd data={contactPageSchema()} />
      <PageHeader title={t("contact.title")} description={t("contact.subtitle")} />

      <SectionWrapper>
        <div className="mx-auto max-w-5xl grid gap-12 md:grid-cols-5">
          {/* Form */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="md:col-span-3"
          >
            <Card>
              <CardContent className="p-6">
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">{t("contact.name")}</Label>
                      <Input id="name" placeholder={t("contact.namePlaceholder")} {...register("name")} />
                      {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">{t("contact.email")}</Label>
                      <Input id="email" type="email" placeholder={t("contact.emailPlaceholder")} {...register("email")} />
                      {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="subject">{t("contact.subject")}</Label>
                    <Input id="subject" placeholder={t("contact.subjectPlaceholder")} {...register("subject")} />
                    {errors.subject && <p className="text-xs text-destructive">{errors.subject.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="message">{t("contact.message")}</Label>
                    <Textarea id="message" rows={5} placeholder={t("contact.messagePlaceholder")} {...register("message")} />
                    {errors.message && <p className="text-xs text-destructive">{errors.message.message}</p>}
                  </div>
                  <Button type="submit" disabled={isSubmitting} className="w-full">
                    {isSubmitting ? t("contact.sending") : t("contact.send")}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* Contact Info */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="md:col-span-2 space-y-4"
          >
            {contactInfo.map((info, i) => (
              <motion.div
                key={info.label}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 + i * 0.1 }}
              >
                <Card>
                  <CardContent className="flex items-center gap-4 p-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <info.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">{info.label}</p>
                      <p className="text-sm font-medium">{info.value}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Contact Methods */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-10"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("contact.methods")}</h2>
          <p className="mt-2 text-muted-foreground">{t("contact.methodsSubtitle")}</p>
        </motion.div>
        <div className="mx-auto max-w-4xl grid gap-6 sm:grid-cols-2">
          {contactMethods.map((method, i) => (
            <motion.div
              key={method.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="p-6 text-center">
                  <div className="flex justify-center mb-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                      <method.icon className="h-6 w-6 text-primary" />
                    </div>
                  </div>
                  <h3 className="font-semibold">{method.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{method.description}</p>
                  <p className="mt-3 text-sm font-medium">{method.detail}</p>
                  <Badge variant="secondary" className="mt-3">{method.badge}</Badge>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>


      {/* Knowledge Base & FAQ */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-4xl grid gap-6 md:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <Card className="h-full">
              <CardContent className="p-6 sm:p-8">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                    <BookOpen className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{t("contact.knowledgeBase")}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {t("contact.knowledgeBaseDesc")}
                    </p>
                    <Button variant="outline" size="sm" className="mt-3" asChild>
                      <Link to="/docs">
                        {t("contact.browseDocs")}
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card className="h-full">
              <CardContent className="p-6 sm:p-8">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                    <MessageCircle className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{t("contact.commonQuestions")}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {t("contact.commonQuestionsDesc")}
                    </p>
                    <Button variant="outline" size="sm" className="mt-3" asChild>
                      <Link to="/faq">
                        {t("contact.viewFaq")}
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
