import { http, HttpResponse } from "msw"
import type { Subscription, SubscriptionPlan } from "@/types"

const mockSubscription: Subscription = {
  id: "sub-1",
  company_id: "company-1",
  billing_term: "monthly",
  status: "active",
  licensed_truck_count: 10,
  pending_truck_count: undefined,
  ai_copilot_enabled: false,
  priority_support_enabled: false,
  api_access_enabled: false,
  price_per_truck_erp_cents: 2900,
  price_per_truck_ai_cents: 1500,
  priority_support_price_cents: 2900,
  api_access_price_cents: 1900,
  annual_discount_pct: 15,
  current_period_start: "2026-07-01T00:00:00Z",
  current_period_end: "2026-08-01T00:00:00Z",
  trial_ends_at: undefined,
  payment_deferred_until: undefined,
  service_credit_cents: 0,
  stripe_customer_id: "cus_mock",
  stripe_subscription_id: "sub_mock",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
}

const mockPlans: SubscriptionPlan[] = [
  {
    id: "plan-starter",
    name: "Starter",
    description: "For small teams getting started with barcode scanning",
    price_per_truck_monthly_cents: 2900,
    price_per_truck_annual_cents: 2465,
    ai_copilot_monthly_cents: 1500,
    ai_copilot_annual_cents: 1275,
    annual_discount_pct: 15,
    features: [
      "Up to 5 team members",
      "Basic barcode scanning",
      "Standard label printing",
      "Email support",
    ],
  },
  {
    id: "plan-professional",
    name: "Professional",
    description: "For growing businesses that need advanced features",
    price_per_truck_monthly_cents: 9900,
    price_per_truck_annual_cents: 8415,
    ai_copilot_monthly_cents: 1500,
    ai_copilot_annual_cents: 1275,
    annual_discount_pct: 15,
    features: [
      "Up to 50 team members",
      "Advanced OCR scanning",
      "Custom label templates",
      "API access",
      "Priority support",
      "Analytics dashboard",
    ],
  },
  {
    id: "plan-enterprise",
    name: "Enterprise",
    description: "For large organizations with custom requirements",
    price_per_truck_monthly_cents: 29900,
    price_per_truck_annual_cents: 25415,
    ai_copilot_monthly_cents: 1500,
    ai_copilot_annual_cents: 1275,
    annual_discount_pct: 15,
    features: [
      "Unlimited team members",
      "AI-powered scanning",
      "Custom integrations",
      "Dedicated account manager",
      "SLA guarantee",
      "On-premise deployment option",
    ],
  },
]

export const subscriptionsHandlers = [
  http.get("*/api/v1/subscriptions/current", () => {
    return HttpResponse.json(mockSubscription)
  }),

  http.get("*/api/v1/subscriptions/plans", () => {
    return HttpResponse.json(mockPlans)
  }),

  http.post("*/api/v1/subscriptions/cancel", () => {
    return HttpResponse.json({
      usable_until: mockSubscription.current_period_end,
    })
  }),

  http.post("*/api/v1/subscriptions/reactivate", () => {
    return HttpResponse.json({
      ...mockSubscription,
      status: "active",
    })
  }),

  http.post("*/api/v1/subscriptions/billing-term", () => {
    return HttpResponse.json({
      ...mockSubscription,
      billing_term: "annual",
    })
  }),

  http.post("*/api/v1/subscriptions/trucks/add", () => {
    return HttpResponse.json({
      ...mockSubscription,
      licensed_truck_count: mockSubscription.licensed_truck_count + 1,
    })
  }),

  http.post("*/api/v1/subscriptions/trucks/remove", () => {
    return HttpResponse.json({
      ...mockSubscription,
      licensed_truck_count: Math.max(0, mockSubscription.licensed_truck_count - 1),
    })
  }),

  http.post("*/api/v1/subscriptions/checkout", () => {
    return HttpResponse.json({
      url: "https://checkout.stripe.com/c/pay/cs_test_mock",
      session_id: "cs_test_mock",
    })
  }),
]
