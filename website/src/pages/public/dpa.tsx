import type { ReactNode } from "react"
import { useLocale } from "@/i18n/locale-context"
import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"

// DPA content is a controlled draft template (business/counsel deliverable) —
// see public/dpa/operion-dpa.md. It is bundled as a raw string via Vite's
// `?raw` import and rendered below with the site's typography. No markdown
// dependency is introduced: the document is a fixed draft, so a small block
// parser (headings, paragraphs, blockquotes, lists, tables, rules) plus
// **bold** / [text](url) inline tokens is enough.
import dpaMarkdown from "../../../public/dpa/operion-dpa.md?raw"

// Same Tailwind Typography treatment used for public blog articles so the
// document reads like first-party copy.
const proseClasses = `prose prose-gray max-w-none dark:prose-invert
  prose-headings:font-bold prose-headings:tracking-tight
  prose-h2:text-2xl prose-h2:mt-12 prose-h2:mb-5 prose-h2:pb-2 prose-h2:border-b prose-h2:border-border/50
  prose-h3:text-xl prose-h3:mt-10 prose-h3:mb-4
  prose-p:text-base prose-p:leading-[1.75] prose-p:mb-5
  prose-li:text-base prose-li:leading-[1.75] prose-li:my-1.5
  prose-strong:font-semibold
  prose-a:text-primary prose-a:no-underline hover:prose-a:underline
  prose-table:w-full prose-table:border-collapse prose-table:my-8
  prose-th:bg-muted prose-th:font-semibold prose-th:text-left prose-th:px-4 prose-th:py-3 prose-th:text-sm prose-th:border prose-th:border-border
  prose-td:px-4 prose-td:py-3 prose-td:text-sm prose-td:border prose-td:border-border
  prose-tr:even:bg-muted/30
  prose-blockquote:border-l-primary prose-blockquote:bg-muted/30 prose-blockquote:py-1 prose-blockquote:px-5 prose-blockquote:rounded-r-lg
  prose-ol:pl-6 prose-ul:pl-6`

type MarkdownBlock =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "blockquote"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "hr" }

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = []
  const lines = markdown.replace(/\r\n/g, "\n").split("\n")

  let i = 0
  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === "") {
      i++
      continue
    }

    // ATX heading (# / ## / ###)
    const heading = /^(#{1,3})\s+(.*)$/.exec(line)
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1].length as 1 | 2 | 3,
        text: heading[2].trim(),
      })
      i++
      continue
    }

    // Horizontal rule
    if (/^-{3,}\s*$/.test(line)) {
      blocks.push({ kind: "hr" })
      i++
      continue
    }

    // Blockquote (consecutive > lines, joined)
    if (line.trim().startsWith(">")) {
      const quoteLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, "").trim())
        i++
      }
      blocks.push({ kind: "blockquote", text: quoteLines.filter(Boolean).join(" ") })
      continue
    }

    // Pipe table (consecutive | lines; row 2 is the separator row)
    if (line.trim().startsWith("|")) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim())
        i++
      }
      if (tableLines.length >= 2) {
        const parseRow = (raw: string) =>
          raw.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim())
        blocks.push({
          kind: "table",
          header: parseRow(tableLines[0]),
          rows: tableLines.slice(2).map(parseRow),
        })
      } else {
        blocks.push({ kind: "paragraph", text: tableLines.join(" ") })
      }
      continue
    }

    // Unordered list (consecutive "- " items)
    if (/^\s*-\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*-\s+/, "").trim())
        i++
      }
      blocks.push({ kind: "list", items })
      continue
    }

    // Paragraph: accumulate until a blank line or the next block opener
    const paragraph: string[] = [line.trim()]
    i++
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,3})\s/.test(lines[i]) &&
      !lines[i].trim().startsWith("|") &&
      !/^\s*-\s+/.test(lines[i]) &&
      !lines[i].trim().startsWith(">") &&
      !/^-{3,}\s*$/.test(lines[i])
    ) {
      paragraph.push(lines[i].trim())
      i++
    }
    blocks.push({ kind: "paragraph", text: paragraph.join(" ") })
  }

  return blocks
}

/** Inline markdown: **bold** and [text](url) links. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\n]+\))/g)
  return tokens.map((token, i) => {
    if (/^\*\*[^*\n]+\*\*$/.test(token)) {
      return <strong key={`${keyPrefix}-${i}`}>{token.slice(2, -2)}</strong>
    }
    const link = /^\[([^\]\n]+)\]\(([^)\n]+)\)$/.exec(token)
    if (link) {
      return (
        <a key={`${keyPrefix}-${i}`} href={link[2]} className="font-medium text-primary underline underline-offset-4">
          {link[1]}
        </a>
      )
    }
    return token
  })
}

function renderBlocks(blocks: MarkdownBlock[]): ReactNode[] {
  return blocks.map((block, i) => {
    switch (block.kind) {
      case "heading":
        // The document's own H1 is covered by the page header, so only render
        // H2/H3 sections to keep a single H1 per page.
        if (block.level === 1) return null
        if (block.level === 2) {
          return <h2 key={i}>{renderInline(block.text, `h2-${i}`)}</h2>
        }
        return <h3 key={i}>{renderInline(block.text, `h3-${i}`)}</h3>
      case "paragraph":
        return <p key={i}>{renderInline(block.text, `p-${i}`)}</p>
      case "blockquote":
        return <blockquote key={i}>{renderInline(block.text, `q-${i}`)}</blockquote>
      case "list":
        return (
          <ul key={i}>
            {block.items.map((item, j) => (
              <li key={j}>{renderInline(item, `li-${i}-${j}`)}</li>
            ))}
          </ul>
        )
      case "table":
        return (
          <div key={i} className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  {block.header.map((cell, j) => (
                    <th key={j}>{cell}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, j) => (
                  <tr key={j}>
                    {row.map((cell, k) => (
                      <td key={k}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      case "hr":
        return <hr key={i} />
      default:
        return null
    }
  })
}

export default function DpaPage() {
  const { t } = useLocale()

  return (
    <>
      <SeoHead
        title={t("trust.dpaTitle")}
        description={t("trust.dpaDraftSeo")}
        canonical="https://operionerp.xyz/dpa"
      />
      {/* PageHeader keeps trust.dpaContent (standard-DPA availability copy shared
          with the trust page); the SEO description uses the draft-accurate
          trust.dpaDraftSeo so search snippets don't over-promise a signed DPA
          while this page shows the draft template. */}
      <PageHeader title={t("trust.dpaTitle")} description={t("trust.dpaContent")} />

      <SectionWrapper>
        <div className={proseClasses}>{renderBlocks(parseMarkdown(dpaMarkdown))}</div>
      </SectionWrapper>
    </>
  )
}