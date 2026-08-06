import { useState } from "react"
import { motion } from "motion/react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label, Textarea } from "@/components/ui/input"
import { Callout } from "@/components/ui/callout"
import { useLocale } from "@/i18n/locale-context"
import { waitlistApi } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { Megaphone, Send, CheckCircle2, Loader2, AlertCircle } from "lucide-react"

const SEGMENTS = [
  { value: "all", labelKey: "admin.waitlist.entries.filter.allStatuses" },
  { value: "joined", labelKey: "admin.waitlist.entries.status.joined" },
  { value: "invited", labelKey: "admin.waitlist.entries.status.invited" },
  { value: "activated", labelKey: "admin.waitlist.entries.status.activated" },
  { value: "converted", labelKey: "admin.waitlist.entries.status.converted" },
  { value: "churned", labelKey: "admin.waitlist.entries.status.churned" },
  { value: "unsubscribed", labelKey: "admin.waitlist.entries.status.unsubscribed" },
]

export default function CampaignTab() {
  const { t } = useLocale()
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [segment, setSegment] = useState("all")
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<{
    status: "success" | "error" | "no_recipients"
    count?: number
    total?: number
    errors?: number
    message?: string
  } | null>(null)

  async function handleSend() {
    if (!subject.trim() || !body.trim()) return

    setSending(true)
    setResult(null)

    try {
      const res = await waitlistApi.sendCampaign({
        subject: subject.trim(),
        body: body.trim(),
        segment,
      })
      const data = res.data
      if (data.status === "sent") {
        setResult({
          status: "success",
          count: data.count,
          total: data.total_recipients,
          errors: data.errors,
        })
        setSubject("")
        setBody("")
      } else if (data.status === "no_recipients") {
        setResult({ status: "no_recipients" })
      } else {
        setResult({ status: "error", message: t("admin.waitlist.campaign.failedToSend") })
      }
    } catch (err) {
      setResult({ status: "error", message: extractApiError(err) })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Megaphone className="h-5 w-5" />
            {t("admin.waitlist.campaign.title")}
          </CardTitle>
          <CardDescription>{t("admin.waitlist.campaign.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Segment selector */}
          <div className="space-y-2">
            <Label>{t("admin.waitlist.entries.filter.status")}</Label>
            <select
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {SEGMENTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {t(s.labelKey)}
                </option>
              ))}
            </select>
          </div>

          {/* Subject */}
          <div className="space-y-2">
            <Label htmlFor="campaign-subject">{t("admin.waitlist.campaign.subject")}</Label>
            <Input
              id="campaign-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder={t("admin.waitlist.campaign.subjectPlaceholder")}
              maxLength={200}
            />
          </div>

          {/* Body */}
          <div className="space-y-2">
            <Label htmlFor="campaign-body">{t("admin.waitlist.campaign.body")}</Label>
            <Textarea
              id="campaign-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("admin.waitlist.campaign.bodyPlaceholder")}
              rows={8}
              className="min-h-[160px]"
            />
          </div>

          {/* Send button */}
          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={handleSend}
              disabled={sending || !subject.trim() || !body.trim()}
              size="lg"
            >
              {sending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("admin.waitlist.campaign.sending")}
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  {t("admin.waitlist.campaign.sendCampaign")}
                </>
              )}
            </Button>
          </div>

          {/* Result feedback */}
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {result.status === "success" && (
                <Callout variant="success" title={t("admin.waitlist.campaign.sent")}>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <span>
                      {t("admin.waitlist.campaign.sentTo")
                        .replace("{count}", String(result.count))
                        .replace("{total}", String(result.total))}
                      {result.errors && result.errors > 0
                        ? ` ${t("admin.waitlist.campaign.errors").replace("{errors}", String(result.errors))}`
                        : ""}
                      .
                    </span>
                  </div>
                </Callout>
              )}
              {result.status === "no_recipients" && (
                <Callout variant="warning" title={t("admin.waitlist.campaign.noRecipients")}>
                  {t("admin.waitlist.campaign.noRecipientsDesc")}
                </Callout>
              )}
              {result.status === "error" && (
                <Callout variant="danger" title={t("admin.waitlist.campaign.sendFailed")}>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    <span>{result.message}</span>
                  </div>
                </Callout>
              )}
            </motion.div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
