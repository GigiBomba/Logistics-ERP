import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Megaphone } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"

export default function CampaignTab() {
  const { t } = useLocale()
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Megaphone className="h-5 w-5" />
          {t("adminWaitlist.campaign.title")}
        </CardTitle>
        <CardDescription>{t("adminWaitlist.campaign.desc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {t("adminWaitlist.campaign.comingSoon")}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("adminWaitlist.campaign.comingSoonDesc")}
        </p>
      </CardContent>
    </Card>
  )
}
