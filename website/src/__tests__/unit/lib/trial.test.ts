import { describe, it, expect } from "vitest"
import { getTrialState, daysLeftInTrial, TRIAL_EXPIRING_SOON_DAYS } from "@/lib/trial"
import type { Subscription } from "@/types"

const MS_PER_DAY = 24 * 60 * 60 * 1000

function makeSub(overrides: Omit<Partial<Subscription>, "trial_ends_at"> & { trial_ends_at?: string | null } = {}): Pick<Subscription, "status"> & { trial_ends_at?: string | null } {
  return {
    id: "sub_1",
    company_id: "comp_1",
    billing_term: "monthly",
    status: "trialing",
    licensed_truck_count: 5,
    pending_truck_count: 0,
    ai_copilot_enabled: false,
    priority_support_enabled: false,
    api_access_enabled: false,
    price_per_truck_erp_cents: 9900,
    price_per_truck_ai_cents: 4900,
    priority_support_price_cents: 0,
    api_access_price_cents: 0,
    annual_discount_pct: 0,
    service_credit_cents: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

function inDays(n: number): string {
  return new Date(Date.now() + n * MS_PER_DAY).toISOString()
}

function inHours(n: number): string {
  return new Date(Date.now() + n * 60 * 60 * 1000).toISOString()
}

describe("getTrialState", () => {
  it("returns 'active' for a trial ending well in the future", () => {
    expect(getTrialState(makeSub({ trial_ends_at: inDays(30) }))).toBe("active")
  })

  it("returns 'expired' for a past trial while status is still 'trialing'", () => {
    const sub = makeSub({ status: "trialing", trial_ends_at: inDays(-1) })
    expect(getTrialState(sub)).toBe("expired")
  })

  it("returns 'active' for a past trial when the server says 'active' (trust server)", () => {
    const sub = makeSub({ status: "active", trial_ends_at: inDays(-5) })
    expect(getTrialState(sub)).toBe("active")
  })

  it("returns 'expiring_soon' for a trial ending in 2 days while trialing", () => {
    const sub = makeSub({ status: "trialing", trial_ends_at: inDays(2) })
    expect(getTrialState(sub)).toBe("expiring_soon")
  })

  it("returns 'active' for null trial_ends_at", () => {
    expect(getTrialState(makeSub({ trial_ends_at: null }))).toBe("active")
  })

  it("returns 'active' for undefined trial_ends_at", () => {
    expect(getTrialState(makeSub({ trial_ends_at: undefined }))).toBe("active")
  })

  it("returns 'active' for an invalid date string", () => {
    expect(getTrialState(makeSub({ trial_ends_at: "not-a-date" }))).toBe("active")
  })

  it("returns 'expired' when the trial ended just now (0 days remaining)", () => {
    // Documented choice: a trial_ends_at at or before now is expired.
    const sub = makeSub({ status: "trialing", trial_ends_at: new Date(Date.now() - 1000).toISOString() })
    expect(getTrialState(sub)).toBe("expired")
  })

  it("returns 'active' for an expiring trial once the server moved off 'trialing'", () => {
    const sub = makeSub({ status: "canceled", trial_ends_at: inDays(1) })
    expect(getTrialState(sub)).toBe("active")
  })

  it(`returns 'expiring_soon' for exactly TRIAL_EXPIRING_SOON_DAYS (${TRIAL_EXPIRING_SOON_DAYS}) days remaining`, () => {
    const sub = makeSub({ status: "trialing", trial_ends_at: inDays(TRIAL_EXPIRING_SOON_DAYS) })
    expect(getTrialState(sub)).toBe("expiring_soon")
  })

  it("treats the last partial day as expiring_soon (ceil semantics)", () => {
    // ~23h remaining is still within the final day
    const sub = makeSub({ status: "trialing", trial_ends_at: inHours(23) })
    expect(getTrialState(sub)).toBe("expiring_soon")
  })
})

describe("daysLeftInTrial", () => {
  it("returns whole days left for a future trial", () => {
    expect(daysLeftInTrial(makeSub({ trial_ends_at: inDays(2) }))).toBe(2)
  })

  it("returns null for null trial_ends_at", () => {
    expect(daysLeftInTrial(makeSub({ trial_ends_at: null }))).toBeNull()
  })

  it("returns null for undefined trial_ends_at", () => {
    expect(daysLeftInTrial(makeSub({ trial_ends_at: undefined }))).toBeNull()
  })

  it("returns null for an invalid date string", () => {
    expect(daysLeftInTrial(makeSub({ trial_ends_at: "garbage" }))).toBeNull()
  })

  it("clamps to 0 once the trial is in the past", () => {
    expect(daysLeftInTrial(makeSub({ trial_ends_at: inDays(-1) }))).toBe(0)
  })
})

describe("TRIAL_EXPIRING_SOON_DAYS", () => {
  it("is 4 days", () => {
    expect(TRIAL_EXPIRING_SOON_DAYS).toBe(4)
  })
})
