import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Megaphone } from "lucide-react"

export default function CampaignTab() {
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Megaphone className="h-5 w-5" />
          Campaign Sending
        </CardTitle>
        <CardDescription>Mass outreach to waitlist segments</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Campaign sending will be available in the next release.
        </p>
        <p className="text-sm text-muted-foreground">
          This feature will allow you to send targeted email campaigns to specific waitlist
          segments — for example, inviting a batch of users, re-engaging churned entries, or
          announcing product updates to activated accounts.
        </p>
      </CardContent>
    </Card>
  )
}
