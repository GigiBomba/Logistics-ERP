import { http, HttpResponse } from "msw"
import type { ChangelogEntry } from "@/types"

const mockChangelog: ChangelogEntry[] = [
  {
    version: "2.5.0",
    release_date: "2026-07-20",
    sections: [
      {
        type: "added",
        items: [
          "AI-powered OCR engine for automatic package label recognition",
          "Batch scanning mode for processing multiple items at once",
          "Offline mode support for remote warehouse operations",
          "New analytics dashboard with real-time throughput metrics",
        ],
      },
      {
        type: "changed",
        items: [
          "Improved barcode scanning speed by 40%",
          "Redesigned settings panel with better organization",
          "Updated API rate limits for enterprise customers",
        ],
      },
      {
        type: "fixed",
        items: [
          "Fixed rare crash when scanning damaged barcodes",
          "Fixed sync issue with slow network connections",
          "Corrected timezone handling in audit logs",
        ],
      },
    ],
    known_issues: ["Mobile app may experience longer sync times on 3G networks"],
  },
  {
    version: "2.4.1",
    release_date: "2026-06-10",
    sections: [
      {
        type: "fixed",
        items: [
          "Fixed authentication token refresh issue",
          "Resolved memory leak in long-running scanning sessions",
          "Fixed print label alignment for 4x6 labels",
        ],
      },
      {
        type: "changed",
        items: ["Updated dependency packages for security patches"],
      },
    ],
  },
  {
    version: "2.4.0",
    release_date: "2026-05-15",
    sections: [
      {
        type: "added",
        items: [
          "Multi-warehouse support",
          "Custom label templates",
          "Role-based access control for team management",
        ],
      },
      {
        type: "changed",
        items: [
          "Enhanced search with fuzzy matching",
          "Faster initial sync for large inventories",
        ],
      },
      {
        type: "removed",
        items: ["Deprecated legacy CSV export format"],
      },
    ],
  },
]

export const changelogHandlers = [
  http.get("*/api/v1/changelog", ({ request }) => {
    const url = new URL(request.url)
    const limit = Number(url.searchParams.get("limit")) || mockChangelog.length
    return HttpResponse.json(mockChangelog.slice(0, limit))
  }),

  http.get("*/api/v1/changelog/:version", ({ params }) => {
    const entry = mockChangelog.find((e) => e.version === params.version)
    if (!entry) {
      return HttpResponse.json({ detail: "Changelog entry not found" }, { status: 404 })
    }
    return HttpResponse.json(entry)
  }),
]
