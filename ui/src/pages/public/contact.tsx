import { Helmet } from "react-helmet-async"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { motion } from "motion/react"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input, Label, Textarea } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  Mail,
  Phone,
  MapPin,
  Clock,
  Send,
  AlertCircle,
} from "lucide-react"

const contactSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Please enter a valid email address"),
  subject: z.string().min(5, "Subject must be at least 5 characters"),
  message: z.string().min(10, "Message must be at least 10 characters"),
})

type ContactFormData = z.infer<typeof contactSchema>

const contactInfo = [
  {
    icon: Mail,
    label: "Email",
    value: "support@operion.com",
    href: "mailto:support@operion.com",
  },
  {
    icon: Phone,
    label: "Phone",
    value: "+40 123 456 789",
    href: "tel:+40123456789",
  },
  {
    icon: MapPin,
    label: "Office",
    value: "Bucharest, Romania",
    href: null,
  },
  {
    icon: Clock,
    label: "Hours",
    value: "Monday-Friday, 9:00-18:00 EET",
    href: null,
  },
]

function ContactForm() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
  })

  const onSubmit = async (_data: ContactFormData) => {
    // Simulate a brief delay
    await new Promise((resolve) => setTimeout(resolve, 600))
    toast.success("Message sent! We'll get back to you within 24 hours.")
    reset()
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          placeholder="Your full name"
          {...register("name")}
          className={cn(errors.name && "border-destructive focus-visible:ring-destructive")}
        />
        {errors.name && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          {...register("email")}
          className={cn(errors.email && "border-destructive focus-visible:ring-destructive")}
        />
        {errors.email && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="subject">Subject</Label>
        <Input
          id="subject"
          placeholder="What is this about?"
          {...register("subject")}
          className={cn(errors.subject && "border-destructive focus-visible:ring-destructive")}
        />
        {errors.subject && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {errors.subject.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="message">Message</Label>
        <Textarea
          id="message"
          placeholder="Tell us more about your inquiry..."
          {...register("message")}
          className={cn(errors.message && "border-destructive focus-visible:ring-destructive")}
        />
        {errors.message && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {errors.message.message}
          </p>
        )}
      </div>

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting ? (
          "Sending..."
        ) : (
          <>
            Send message
            <Send className="ml-2 h-4 w-4" />
          </>
        )}
      </Button>
    </form>
  )
}

function ContactInfoCard({
  icon: Icon,
  label,
  value,
  href,
  index,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  href: string | null
  index: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="flex items-start gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          {href ? (
            <a
              href={href}
              className="mt-1 block text-sm font-medium text-foreground transition-colors hover:text-primary"
            >
              {value}
            </a>
          ) : (
            <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
          )}
        </div>
      </Card>
    </motion.div>
  )
}

export default function ContactPage() {
  return (
    <>
      <Helmet>
        <title>Contact - Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        <PageHeader
          title="Get in Touch"
          description="Have questions? We'd love to hear from you. Reach out and we'll get back to you within 24 hours."
          className="text-center"
        />

        <div className="mt-16 grid gap-10 lg:grid-cols-2 lg:gap-16">
          {/* Left: Form */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <ContactForm />
          </motion.div>

          {/* Right: Contact Info */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="space-y-4"
          >
            {contactInfo.map((info, index) => (
              <ContactInfoCard key={info.label} {...info} index={index} />
            ))}
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
