import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router"
import { useLocale } from "@/i18n/locale-context"
import { motion } from "motion/react"
import { useState } from "react"
import { ArrowLeft, Clock, ThumbsUp, ThumbsDown, BookOpen, Star, Video, Code } from "lucide-react"
import { Breadcrumbs } from "@/components/ui/breadcrumbs"
import { CopyButton } from "@/components/ui/copy-button"
import { Callout, type CalloutVariant } from "@/components/ui/callout"
import { Tag } from "@/components/ui/tag"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { docsConfig } from "@/config/site"

// ─── Types ─────────────────────────────────────────────────────────

interface ArticleData {
  title: string
  category: string
  categorySlug: string
  content: string
  tags?: string[]
  related?: string[]
  version?: string
  hasVideo?: boolean
}

// ─── Utils ──────────────────────────────────────────────────────────

function slugify(str: string) {
  return str
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]/g, "")
}

function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length
}

function readingTime(text: string): number {
  const wpm = docsConfig.readingSpeedWPM
  return Math.ceil(wordCount(text) / wpm)
}

// ─── Inline processing ──────────────────────────────────────────────

function processInline(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code class="bg-muted/80 px-[5px] py-[2px] rounded text-sm font-mono text-foreground before:content-none after:content-none">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong class='font-semibold'>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary font-medium hover:underline" target="_blank" rel="noopener noreferrer">$1</a>')
}

// ─── Content Parser ─────────────────────────────────────────────────

function parseContent(content: string) {
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let idx = 0
  let keyCounter = 0

  while (idx < lines.length) {
    const line = lines[idx]
    const key = keyCounter++

    // ── Callout blocks ──
    const calloutMatch = line.match(/^:::(\w+)\s*(.*)$/)
    if (calloutMatch) {
      const variant = calloutMatch[1] as CalloutVariant
      const title = calloutMatch[2].trim() || undefined
      const calloutLines: string[] = []
      idx++
      while (idx < lines.length && !lines[idx].startsWith(":::")) {
        calloutLines.push(lines[idx])
        idx++
      }
      if (idx < lines.length && lines[idx].startsWith(":::")) idx++ // skip ::: end

      const bodyText = calloutLines.join(" ").trim()
      elements.push(
        <Callout key={key} variant={variant} title={title}>
          <p>{bodyText}</p>
        </Callout>
      )
      continue
    }

    // ── Headings ──
    if (line.startsWith("## ")) {
      const text = line.slice(3).trim()
      const id = slugify(text)
      elements.push(
        <h2 key={key} id={id} className="scroll-mt-24 text-xl font-bold mt-10 mb-4 tracking-tight">
          {text}
        </h2>
      )
      idx++
      continue
    }
    if (line.startsWith("### ")) {
      const text = line.slice(4).trim()
      const id = slugify(text)
      elements.push(
        <h3 key={key} id={id} className="scroll-mt-24 text-lg font-semibold mt-8 mb-3 tracking-tight">
          {text}
        </h3>
      )
      idx++
      continue
    }

    // ── Bullet lists ──
    if (line.startsWith("- ")) {
      const items: string[] = []
      while (idx < lines.length && lines[idx].startsWith("- ")) {
        items.push(lines[idx].slice(2))
        idx++
      }
      elements.push(
        <ul key={key} className="my-3 ml-6 space-y-1.5 list-disc [&_li]:text-muted-foreground [&_li]:leading-relaxed">
          {items.map((item, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: processInline(item) }} />
          ))}
        </ul>
      )
      continue
    }

    // ── Numbered lists ──
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = []
      while (idx < lines.length && /^\d+\.\s/.test(lines[idx])) {
        items.push(lines[idx].replace(/^\d+\.\s/, ""))
        idx++
      }
      elements.push(
        <ol key={key} className="my-3 ml-6 space-y-1.5 list-decimal [&_li]:text-muted-foreground [&_li]:leading-relaxed">
          {items.map((item, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: processInline(item) }} />
          ))}
        </ol>
      )
      continue
    }

    // ── Bold paragraph (line starting with **) ──
    if (line.startsWith("**") && line.includes("** —")) {
      // e.g. **Run the installer** — Double-click...
      const processed = processInline(line)
      elements.push(
        <p key={key} className="text-muted-foreground leading-relaxed mb-3" dangerouslySetInnerHTML={{ __html: processed }} />
      )
      idx++
      continue
    }

    // ── Empty line ──
    if (line.trim() === "") {
      elements.push(<div key={key} className="h-2" />)
      idx++
      continue
    }

    // ── Regular paragraph ──
    const processed = processInline(line)
    elements.push(
      <p key={key} className="text-muted-foreground leading-[1.75] mb-3" dangerouslySetInnerHTML={{ __html: processed }} />
    )
    idx++
  }

  return elements
}

// ─── Article Data ───────────────────────────────────────────────────

const articles: Record<string, ArticleData> = {
  installation: {
    title: "Installing Operion ERP",
    category: "Getting Started",
    categorySlug: "getting-started",
    tags: ["installation", "setup", "Windows"],
    related: ["creating-account", "first-route"],
    version: "v1.0+",
    hasVideo: true,
    content: `## Before You Begin

Make sure your system meets the minimum requirements:

- Windows 10 (64-bit) or Windows 11 (64-bit)
- 8 GB RAM (16 GB recommended)
- 2 GB available disk space
- Intel Core i5 or equivalent processor
- .NET Framework 4.8 or later

:::warning System Requirements
Ensure your system meets all minimum requirements before proceeding. Installation on unsupported hardware may cause performance issues.
:::

## Download the Installer

1. Go to the [Downloads page](/download) and click "Download for Windows".
2. Save the installer file (\`operion-setup-1.0.0.exe\`) to your computer.

## Installation Steps

1. **Run the installer** — Double-click the downloaded file.
2. **Accept the license agreement** — Read and accept the Terms of Service.
3. **Choose installation location** — The default location is recommended.
4. **Click Install** — The setup wizard will install Operion and all required components.
5. **Launch Operion** — Once installation completes, click "Finish" to launch.

:::success Installation Complete
Operion is now installed. Proceed to the "Creating Your Account" guide to set up your workspace.
:::

## First Launch

When you first launch Operion, you'll be prompted to sign in or create a new account. If you're on a trial, you can start exploring immediately.

## Troubleshooting

- **"Missing .NET Framework" error** — Download and install .NET Framework 4.8 from Microsoft's website.
- **Application won't start** — Verify your antivirus isn't blocking Operion. Add an exception if needed.
- **Installation fails** — Run the installer as Administrator by right-clicking and selecting "Run as Administrator".

:::info Need Help?
Visit our [Community Forum](https://community.operionerp.xyz) for additional troubleshooting tips and support from other users.
:::`,
  },
  "first-route": {
    title: "Creating Your First Route",
    category: "Route Planning",
    categorySlug: "route-planning",
    tags: ["routes", "optimization", "beginners"],
    related: ["installation", "multi-stop"],
    version: "v1.0+",
    content: `## Overview

This guide walks you through creating your first delivery route in Operion ERP.

:::success Prerequisites Met
Before starting, ensure Operion ERP is installed and you have at least one vehicle added to your fleet.
:::

## Prerequisites

- Operion ERP installed and configured
- At least one vehicle added to your fleet
- Delivery addresses ready to input

## Step 1: Open the Route Planner

From the main dashboard, click **Route Planning** in the left sidebar, then click **New Route**.

## Step 2: Add Stops

1. Click **Add Stop** to begin building your route.
2. Enter the address for each delivery location.
3. Set the time window for each stop (optional).
4. Add any special instructions or notes.

## Step 3: Optimize

Once all stops are added, click the **Optimize** button. Operion will calculate the most efficient route based on:

- Distance between stops
- Traffic conditions
- Delivery time windows
- Vehicle capacity

:::info Optimization Algorithms
Operion uses a proprietary multi-factor optimization engine that considers live traffic data, historical delivery times, and vehicle specifications.
:::

## Step 4: Assign to Driver

Select a driver from the dropdown and click **Assign**. The route will be sent to the driver's mobile device.

## Step 5: Monitor Progress

Track the route's progress in real-time from the Dispatch dashboard. You can see:

- Current vehicle location
- Completed vs. remaining stops
- Estimated time of arrival

## Tips

- Use **Route Templates** for recurring routes to save time.
- Set **Priority Stops** for time-sensitive deliveries.
- Check weather conditions before finalizing long-distance routes.`,
  },
  "creating-account": {
    title: "Creating Your Account",
    category: "Getting Started",
    categorySlug: "getting-started",
    tags: ["account", "setup", "registration"],
    related: ["installation", "quick-start"],
    version: "v1.0+",
    content: `## Sign Up

1. Visit [operionerp.xyz/register](/register)
2. Enter your name, email, and choose a password.
3. Optionally provide your company name.
4. Click **Create Account**.

## Verify Your Email

Check your inbox for a verification email. Click the link to verify your account. If you don't see it, check your spam folder.

:::warning Email Verification
You must verify your email address within 48 hours. After that, the verification link expires and you'll need to request a new one.
:::

## Set Up Your Company Profile

After verification, sign in and navigate to **Dashboard → Company**. Fill in:

- Company name
- Address
- VAT number (if applicable)
- Contact information

## Choose Your Plan

Visit **Dashboard → Subscription** to select the plan that fits your fleet size. All plans start with a 14-day free trial.

:::success You're All Set
Once your subscription is active, you can invite team members and start managing your fleet operations.
:::`,
  },
}

// ─── Related articles lookup ────────────────────────────────────────

function getRelatedArticles(slugs: string[]): { title: string; slug: string; categorySlug: string; excerpt: string }[] {
  const related: { title: string; slug: string; categorySlug: string; excerpt: string }[] = []
  for (const slug of slugs) {
    const article = articles[slug]
    if (article) {
      related.push({
        title: article.title,
        slug,
        categorySlug: article.categorySlug,
        excerpt: (article.content.split("\n").find((l) => l.trim().length > 20 && !l.startsWith("#") && !l.startsWith(":::")) || "").slice(0, 100),
      })
    }
    if (related.length >= 3) break
  }
  return related
}

// ─── Component ──────────────────────────────────────────────────────

export default function DocsArticlePage() {
  const { t } = useLocale()
  const { slug } = useParams<{ category: string; slug: string }>()
  const key = slug || ""
  const article = articles[key]
  const [rating, setRating] = useState<number | null>(null)
  const [rated, setRated] = useState(false)

  const parsedContent = useMemo(
    () => (article ? parseContent(article.content) : []),
    [article]
  )

  const readTime = useMemo(
    () => (article ? readingTime(article.content) : 0),
    [article]
  )

  const relatedArticles = useMemo(
    () => (article?.related ? getRelatedArticles(article.related) : []),
    [article]
  )

  if (!article) {
    return (
      <>
        <Helmet><title>Article Not Found — Operion ERP</title></Helmet>
        <div className="text-center py-16">
          <h1 className="text-2xl font-bold">Article Not Found</h1>
          <p className="mt-2 text-muted-foreground">{t("docs.articleNotFoundDesc")}</p>
          <Link to="/docs" className="mt-4 inline-block text-primary hover:underline">{t("docs.backToDocs")}</Link>
        </div>
      </>
    )
  }

  return (
    <article>
      <Helmet><title>{`${article.title} — Documentation — Operion ERP`}</title></Helmet>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        {/* Breadcrumbs */}
        <Breadcrumbs
          items={[
            { label: "Docs", href: "/docs" },
            { label: article.category, href: `/docs/${article.categorySlug}` },
            { label: article.title },
          ]}
          className="mb-4"
        />

        {/* Title */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-3xl font-bold tracking-tight">{article.title}</h1>

            {/* Meta info */}
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                <span>{readTime} min read</span>
              </div>
              <span className="text-muted-foreground/30">·</span>
              <span>{t("docs.lastUpdated")}</span>
              {article.version && (
                <>
                  <span className="text-muted-foreground/30">·</span>
                  <span className="inline-flex items-center rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-xs font-medium text-primary">
                    Applies to: Operion {article.version}
                  </span>
                </>
              )}
            </div>

            {/* Tags */}
            {article.tags && article.tags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {article.tags.map((tag) => (
                  <Tag key={tag} variant="outline">{tag}</Tag>
                ))}
              </div>
            )}
          </div>

          {/* Copy article button */}
          <div className="hidden sm:flex shrink-0">
            <CopyButton text={article.content} />
          </div>
        </div>
      </motion.div>

      {/* Content */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mt-8 max-w-none"
      >
        {parsedContent}

        {/* Video tutorial placeholder */}
        {article.hasVideo && (
          <Callout variant="info" icon={<Video className="h-5 w-5 shrink-0 mt-0.5 text-blue-500 dark:text-blue-400" />} className="mt-8">
            <p className="font-medium">{t("docs.videoComingSoon")}</p>
            <p className="text-sm text-muted-foreground">A step-by-step video tutorial for this guide is in production. Check back in a few days.</p>
          </Callout>
        )}
      </motion.div>

      {/* ── Related Articles ── */}
      {relatedArticles.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mt-12 pt-8 border-t"
        >
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            Related Articles
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {relatedArticles.map((ra) => (
              <Link key={ra.slug} to={`/docs/${ra.categorySlug}/${ra.slug}`}>
                <Card className="h-full transition-all hover:shadow-md hover:border-primary/30">
                  <CardContent className="p-4">
                    <h4 className="font-medium text-sm">{ra.title}</h4>
                    {ra.excerpt && (
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{ra.excerpt}…</p>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Was this helpful? ── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="mt-10 p-5 rounded-lg border bg-muted/30"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="font-medium text-sm">{t("docs.wasHelpful")}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t("docs.feedback")}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5">
              <ThumbsUp className="h-3.5 w-3.5" />
              Yes
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5">
              <ThumbsDown className="h-3.5 w-3.5" />
              No
            </Button>
          </div>
        </div>

        {/* Star rating */}
        <div className="mt-5 pt-5 border-t">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <p className="font-medium text-sm">{t("docs.rateArticle")}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {rated ? "Thank you for your feedback." : "How would you rate the quality of this guide?"}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => {
                    setRating(star)
                    setRated(true)
                  }}
                  className="p-1 rounded-md transition-colors hover:bg-muted"
                  aria-label={`Rate ${star} stars`}
                >
                  <Star
                    className={`h-5 w-5 ${
                      rated && rating && star <= rating
                        ? "fill-amber-400 text-amber-400"
                        : "text-muted-foreground/40"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* ── Edit this page ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mt-6 text-center"
      >
        <Button variant="outline" size="sm" className="gap-1.5 inline-flex items-center">
          <Code className="h-3.5 w-3.5" />
          Suggest edits on GitHub
        </Button>
      </motion.div>

      {/* Back link */}
      <div className="mt-8 pt-4 border-t">
        <Link
          to={`/docs/${article.categorySlug}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to {article.category}
        </Link>
      </div>
    </article>
  )
}
