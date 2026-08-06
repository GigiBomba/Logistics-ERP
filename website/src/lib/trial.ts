import type { Subscription } from "@/types"

export type TrialState = "active" | "expiring_soon" | "expired"

/** Number of days before trial end at which we surface the "expiring soon" nudge. */
export const TRIAL_EXPIRING_SOON_DAYS = 4

const MS_PER_DAY = 24 * 60 * 60 * 1000

/**
 * Defensive, display-only classification of a subscription's trial state.
 *
 * The backend is the source of truth for whether a subscription is still on trial
 * (status === "trialing"). We never gate access client-side — this only powers
 * honest banners. Rules:
 *
 * - No trial_ends_at (or an unparseable value) → "active"
 * - trial_ends_at in the future:
 *   - 4 or fewer days remaining AND status === "trialing" → "expiring_soon"
 *   - otherwise → "active"
 * - trial_ends_at in the past:
 *   - status === "trialing" → "expired" (server still thinks we're on trial)
 *   - otherwise → "active" (server has moved us off trial; trust it)
 */
export function getTrialState(subscription: Pick<Subscription, "status"> & { trial_ends_at?: string | null }): TrialState {
  const { status, trial_ends_at } = subscription

  if (trial_ends_at == null || trial_ends_at === "") return "active"

  const trialEnd = new Date(trial_ends_at)
  if (Number.isNaN(trialEnd.getTime())) return "active"

  const daysLeft = (trialEnd.getTime() - Date.now()) / MS_PER_DAY

  if (daysLeft < 0) {
    return status === "trialing" ? "expired" : "active"
  }

  if (daysLeft <= TRIAL_EXPIRING_SOON_DAYS) {
    return status === "trialing" ? "expiring_soon" : "active"
  }

  return "active"
}

/**
 * Whole days left until the trial ends (ceiling, so partial days round up).
 * Returns null when there is no usable trial_ends_at.
 */
export function daysLeftInTrial(subscription: { trial_ends_at?: string | null }): number | null {
  const { trial_ends_at } = subscription

  if (trial_ends_at == null || trial_ends_at === "") return null

  const trialEnd = new Date(trial_ends_at)
  if (Number.isNaN(trialEnd.getTime())) return null

  return Math.max(0, Math.ceil((trialEnd.getTime() - Date.now()) / MS_PER_DAY))
}
