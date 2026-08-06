import { setupServer } from "msw/node"
import { authHandlers } from "./handlers/auth"
import { devicesHandlers } from "./handlers/devices"
import { supportHandlers } from "./handlers/support"
import { organizationsHandlers } from "./handlers/organizations"
import { companyHandlers } from "./handlers/company"
import { notificationsHandlers } from "./handlers/notifications"
import { blogHandlers } from "./handlers/blog"
import { changelogHandlers } from "./handlers/changelog"
import { subscriptionsHandlers } from "./handlers/subscriptions"
import { mfaHandlers } from "./handlers/mfa"
import { waitlistHandlers } from "./handlers/waitlist"

export const server = setupServer(
  ...authHandlers,
  ...devicesHandlers,
  ...supportHandlers,
  ...organizationsHandlers,
  ...companyHandlers,
  ...notificationsHandlers,
  ...blogHandlers,
  ...changelogHandlers,
  ...subscriptionsHandlers,
  ...mfaHandlers,
  ...waitlistHandlers,
)
