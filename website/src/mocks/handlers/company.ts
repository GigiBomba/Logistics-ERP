import { http, HttpResponse } from "msw"
import type { Company } from "@/types"

const mockCompany: Company = {
  id: 1,
  company_name: "Test Company",
  name: "Test Company",
  subscription_tier: "professional",
  is_active: true,
  vat_number: "US123456789",
  address: "123 Main Street",
  city: "New York",
  country: "US",
  postal_code: "10001",
  phone: "+1-555-0100",
  website: "https://testcompany.example.com",
  industry: "Logistics",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-07-01T12:00:00Z",
}

export const companyHandlers = [
  http.get("*/api/v1/settings/company", () => {
    return HttpResponse.json(mockCompany)
  }),

  http.put("*/api/v1/settings/company", async ({ request }) => {
    const body = (await request.json()) as Partial<Company>
    const updated = { ...mockCompany, ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(updated)
  }),

  http.patch("*/api/v1/settings/company", async ({ request }) => {
    const body = (await request.json()) as Partial<Company>
    const updated = { ...mockCompany, ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(updated)
  }),
]
