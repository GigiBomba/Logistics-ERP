#!/usr/bin/env node
// Generates deterministic per-blog-post Open Graph images (1200x630 PNG) with
// zero runtime deps: a minimal PNG encoder built on node:zlib (deflateSync for
// IDAT, CRC32 implemented inline) and a small embedded 5x7 bitmap font.
//
// Layout per image:
//   - vertical gradient background derived from a hash of the slug
//     (dark slate -> blue/purple family palette)
//   - "OPERION" wordmark top-left (bitmap font, small caps)
//   - slug-derived title, uppercase, word-wrapped to ~55 chars/line, up to 3
//     lines, vertically centered
//   - subtle "operionerp.xyz" footer line
//
// Slug source mirrors scripts/generate-sitemap.ts: it fetches
//   https://api.operionerp.xyz/api/v1/blog/posts
// with a 4s AbortController timeout and falls back to a hardcoded seed list
// (the shipped articles) when the API is unreachable or requires auth.
//
// Usage:  npx tsx scripts/generate-og-images.ts
// Output: public/og/blog/{slug}.png

import { deflateSync, inflateSync } from "node:zlib"
import { mkdirSync, writeFileSync, readFileSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = join(__dirname, "..", "public", "og", "blog")

const BLOG_API_URL = "https://api.operionerp.xyz/api/v1/blog/posts"

// Optional build-time auth for the blog API. When set, an
// `Authorization: Bearer <token>` header is sent on the posts fetch so real
// slugs are retrieved instead of falling back to the seed list.
function blogApiToken(): string | undefined {
  return process.env.BLOG_API_TOKEN || process.env.OPERION_BLOG_API_TOKEN || undefined
}

// Hardcoded seed list — mirrors the articles shipped in
// src/pages/public/blog-article.tsx. Used when the public API is unreachable
// (or requires auth) at build time.
const SEED_SLUGS = [
  "operion-ai-copilot-intelligent-logistics-automation",
  "operion-ai-workflow-transformation-non-technical",
  "how-to-calculate-trip-profitability-road-transport",
  "understanding-cost-per-kilometer-transport-manager-guide",
  "fuel-cost-management-strategies-small-fleets",
  "role-of-exchange-rates-international-logistics-profitability",
  "what-makes-transport-route-profitable-vs-unprofitable",
  "financial-kpis-every-logistics-business-should-track",
  "preventive-maintenance-scheduling-small-truck-fleets",
  "tire-management-impact-operating-costs",
  "driver-retention-strategies-transport-companies",
  "telematics-basics-small-fleets-need-to-know",
  "fleet-right-sizing-matching-capacity-to-demand",
  "effective-communication-dispatchers-and-drivers",
  "load-planning-fundamentals-new-dispatchers",
  "managing-detention-time-and-waiting-charges",
  "role-of-the-dispatcher-in-trip-profitability",
  "handling-disruptions-dispatcher-guide-contingency-planning",
]

const WIDTH = 1200
const HEIGHT = 630

// ---- PNG encoder -----------------------------------------------------------

const CRC_TABLE = new Uint32Array(256)
for (let n = 0; n < 256; n++) {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  CRC_TABLE[n] = c >>> 0
}

function crc32(buf: Uint8Array, start = 0, end = buf.length): number {
  let c = 0xffffffff
  for (let i = start; i < end; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function pngChunk(type: string, data: Uint8Array): Uint8Array {
  const out = new Uint8Array(12 + data.length)
  const dv = new DataView(out.buffer)
  dv.setUint32(0, data.length)
  for (let i = 0; i < 4; i++) out[4 + i] = type.charCodeAt(i)
  out.set(data, 8)
  dv.setUint32(8 + data.length, crc32(out, 4, 8 + data.length))
  return out
}

function encodePng(rgba: Uint8Array): Uint8Array {
  // IHDR: width, height, bit depth 8, color type 6 (RGBA), compression 0,
  // filter 0, interlace 0
  const ihdr = new Uint8Array(13)
  const v = new DataView(ihdr.buffer)
  v.setUint32(0, WIDTH)
  v.setUint32(4, HEIGHT)
  ihdr[8] = 8
  ihdr[9] = 6
  ihdr[10] = 0
  ihdr[11] = 0
  ihdr[12] = 0

  const stride = WIDTH * 4
  const raw = new Uint8Array((stride + 1) * HEIGHT)
  for (let y = 0; y < HEIGHT; y++) {
    raw[y * (stride + 1)] = 0 // filter type 0 (None) per scanline
    raw.set(rgba.subarray(y * stride, (y + 1) * stride), y * (stride + 1) + 1)
  }

  const idat = deflateSync(raw, { level: 9 })
  const sig = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
  const parts = [sig, pngChunk("IHDR", ihdr), pngChunk("IDAT", idat), pngChunk("IEND", new Uint8Array(0))]
  const size = parts.reduce((s, p) => s + p.length, 0)
  const out = new Uint8Array(size)
  let off = 0
  for (const p of parts) {
    out.set(p, off)
    off += p.length
  }
  return out
}

// ---- Canvas ----------------------------------------------------------------

type RGB = [number, number, number]

interface Canvas {
  buf: Uint8Array
  set: (x: number, y: number, r: number, g: number, b: number, a?: number) => void
}

function makeCanvas(): Canvas {
  const buf = new Uint8Array(WIDTH * HEIGHT * 4)
  return {
    buf,
    set(x, y, r, g, b, a = 255) {
      if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) return
      const i = (y * WIDTH + x) * 4
      buf[i] = r
      buf[i + 1] = g
      buf[i + 2] = b
      buf[i + 3] = a
    },
  }
}

function fillGradient(buf: Uint8Array, top: RGB, bottom: RGB): void {
  for (let y = 0; y < HEIGHT; y++) {
    const t = y / (HEIGHT - 1)
    const r = Math.round(top[0] + (bottom[0] - top[0]) * t)
    const g = Math.round(top[1] + (bottom[1] - top[1]) * t)
    const b = Math.round(top[2] + (bottom[2] - top[2]) * t)
    for (let x = 0; x < WIDTH; x++) {
      const i = (y * WIDTH + x) * 4
      buf[i] = r
      buf[i + 1] = g
      buf[i + 2] = b
      buf[i + 3] = 255
    }
  }
}

// ---- Deterministic branding -------------------------------------------------

function fnv1a(str: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

// Dark slate tops, blue/purple-family bottoms. Kept tasteful: white text reads
// well on every pair.
const GRADIENTS: Array<[RGB, RGB]> = [
  [[15, 23, 42], [79, 70, 229]], // slate -> indigo
  [[2, 6, 23], [37, 99, 235]], // near-black -> blue
  [[30, 27, 75], [124, 58, 237]], // dark indigo -> violet
  [[17, 24, 39], [8, 145, 178]], // slate -> cyan
  [[23, 37, 84], [29, 78, 216]], // navy -> blue
  [[46, 16, 101], [147, 51, 234]], // deep purple -> purple
]

// ---- 5x7 bitmap font ---------------------------------------------------------
// 7 rows per glyph, 5 columns each. A row byte's bit 4 is the leftmost pixel
// (0x10), bit 0 the rightmost. Only the ASCII subset the labels need is drawn;
// unknown characters render as a space.
const FONT: Record<string, number[]> = {
  A: [0x0e, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11],
  B: [0x1e, 0x11, 0x11, 0x1e, 0x11, 0x11, 0x1e],
  C: [0x0e, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0e],
  D: [0x1c, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1c],
  E: [0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f],
  F: [0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10],
  G: [0x0e, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0f],
  H: [0x11, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11],
  I: [0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1f],
  J: [0x0f, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0c],
  K: [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
  L: [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f],
  M: [0x11, 0x1b, 0x15, 0x15, 0x11, 0x11, 0x11],
  N: [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
  O: [0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e],
  P: [0x1e, 0x11, 0x11, 0x1e, 0x10, 0x10, 0x10],
  Q: [0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d],
  R: [0x1e, 0x11, 0x11, 0x1e, 0x14, 0x12, 0x11],
  S: [0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e],
  T: [0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
  U: [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e],
  V: [0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04],
  W: [0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0a],
  X: [0x11, 0x11, 0x0a, 0x04, 0x0a, 0x11, 0x11],
  Y: [0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04],
  Z: [0x1f, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1f],
  "0": [0x0e, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0e],
  "1": [0x04, 0x0c, 0x04, 0x04, 0x04, 0x04, 0x0e],
  "2": [0x0e, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1f],
  "3": [0x1f, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0e],
  "4": [0x02, 0x06, 0x0a, 0x12, 0x1f, 0x02, 0x02],
  "5": [0x1f, 0x10, 0x1e, 0x01, 0x01, 0x11, 0x0e],
  "6": [0x06, 0x08, 0x10, 0x1e, 0x11, 0x11, 0x0e],
  "7": [0x1f, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
  "8": [0x0e, 0x11, 0x11, 0x0e, 0x11, 0x11, 0x0e],
  "9": [0x0e, 0x11, 0x11, 0x0f, 0x01, 0x02, 0x0c],
  " ": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
  "-": [0x00, 0x00, 0x00, 0x0e, 0x00, 0x00, 0x00],
  ".": [0x00, 0x00, 0x00, 0x00, 0x00, 0x0c, 0x0c],
  "/": [0x01, 0x02, 0x04, 0x08, 0x10, 0x00, 0x00],
  ":": [0x00, 0x0c, 0x0c, 0x00, 0x0c, 0x0c, 0x00],
  ",": [0x00, 0x00, 0x00, 0x00, 0x0c, 0x0c, 0x04],
  "'": [0x0c, 0x0c, 0x04, 0x00, 0x00, 0x00, 0x00],
  '"': [0x0a, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00],
  "(": [0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02],
  ")": [0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08],
  "?": [0x0e, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04],
  "!": [0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04],
  "+": [0x00, 0x04, 0x04, 0x1f, 0x04, 0x04, 0x00],
  "=": [0x00, 0x00, 0x1f, 0x00, 0x1f, 0x00, 0x00],
  _: [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1f],
  "<": [0x01, 0x02, 0x04, 0x08, 0x04, 0x02, 0x01],
  ">": [0x10, 0x08, 0x04, 0x02, 0x04, 0x08, 0x10],
  "#": [0x0a, 0x1f, 0x0a, 0x0a, 0x1f, 0x0a, 0x0a],
  "%": [0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13],
  "&": [0x0c, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0d],
  "@": [0x0e, 0x11, 0x17, 0x15, 0x17, 0x10, 0x0f],
  $: [0x04, 0x0f, 0x14, 0x0e, 0x05, 0x1e, 0x04],
  "*": [0x00, 0x0a, 0x04, 0x1f, 0x04, 0x0a, 0x00],
  "[": [0x0f, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0f],
  "]": [0x0f, 0x01, 0x01, 0x01, 0x01, 0x01, 0x0f],
}

// ---- Drawing ---------------------------------------------------------------

function drawText(
  c: Canvas,
  text: string,
  x: number,
  y: number,
  scale: number,
  color: [number, number, number, number]
): number {
  const [r, g, b, a] = color
  let cx = x
  for (const ch of text.toUpperCase()) {
    const glyph = FONT[ch] ?? FONT[" "]
    for (let row = 0; row < 7; row++) {
      const bits = glyph[row]
      for (let col = 0; col < 5; col++) {
        if (bits & (0x10 >> col)) {
          const px = cx + col * scale
          const py = y + row * scale
          for (let dy = 0; dy < scale; dy++) {
            for (let dx = 0; dx < scale; dx++) c.set(px + dx, py + dy, r, g, b, a)
          }
        }
      }
    }
    cx += 6 * scale // 5px glyph + 1px spacing
  }
  return cx - x
}

function fillRect(c: Canvas, x: number, y: number, w: number, h: number, color: [number, number, number, number]): void {
  const [r, g, b, a] = color
  for (let dy = 0; dy < h; dy++) for (let dx = 0; dx < w; dx++) c.set(x + dx, y + dy, r, g, b, a)
}

function titleFromSlug(slug: string): string {
  return slug
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase()
}

function wrapTitle(title: string, maxWidthPx: number, scale: number): string[] {
  const charW = 6 * scale
  const words = title.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let cur = ""
  for (const w of words) {
    const trial = cur ? `${cur} ${w}` : w
    if (trial.length * charW <= maxWidthPx) {
      cur = trial
    } else {
      if (cur) lines.push(cur)
      if (w.length * charW > maxWidthPx) {
        // single word longer than a line — hard break
        const perLine = Math.max(1, Math.floor(maxWidthPx / charW))
        let rem = w
        while (rem.length * charW > maxWidthPx) {
          lines.push(rem.slice(0, perLine))
          rem = rem.slice(perLine)
        }
        cur = rem
      } else {
        cur = w
      }
    }
  }
  if (cur) lines.push(cur)
  return lines
}

function renderTitle(c: Canvas, title: string, color: [number, number, number, number]): void {
  const maxLines = 3
  const margin = 72
  const maxWidth = WIDTH - margin * 2

  let lines: string[] = []
  let scale = 3
  for (const s of [3, 2, 1]) {
    const wrapped = wrapTitle(title, maxWidth, s)
    if (wrapped.length <= maxLines) {
      lines = wrapped
      scale = s
      break
    }
  }
  if (lines.length === 0) lines = wrapTitle(title, maxWidth, 3)
  if (lines.length > maxLines) lines = lines.slice(0, maxLines)

  const lineGap = 7 * scale + 2 * scale
  const blockH = lines.length * lineGap - 2 * scale
  let y = Math.round((HEIGHT - blockH) / 2)
  for (const line of lines) {
    const w = line.length * 6 * scale
    const x = Math.round((WIDTH - w) / 2)
    drawText(c, line, x, y, scale, color)
    y += lineGap
  }
}

// ---- Verification (self-check after writing) --------------------------------

function verifyPng(filePath: string): void {
  const data = readFileSync(filePath)
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]
  for (let i = 0; i < 8; i++) if (data[i] !== sig[i]) throw new Error(`bad PNG signature: ${filePath}`)

  let pos = 8
  let idat: Uint8Array | null = null
  while (pos < data.length) {
    const len = new DataView(data.buffer, data.byteOffset + pos, 4).getUint32(0)
    const type = String.fromCharCode(data[pos + 4], data[pos + 5], data[pos + 6], data[pos + 7])
    const chunkStart = pos + 8
    if (type === "IHDR") {
      const w = new DataView(data.buffer, data.byteOffset + chunkStart, 4).getUint32(0)
      const h = new DataView(data.buffer, data.byteOffset + chunkStart + 4, 4).getUint32(0)
      if (w !== WIDTH || h !== HEIGHT) throw new Error(`unexpected dimensions ${w}x${h}: ${filePath}`)
    }
    if (type === "IDAT") idat = data.subarray(chunkStart, chunkStart + len)
    pos = chunkStart + len + 4 // skip data + crc
  }
  if (!idat) throw new Error(`no IDAT chunk: ${filePath}`)
  const raw = inflateSync(idat)
  const expected = (WIDTH * 4 + 1) * HEIGHT
  if (raw.length !== expected) throw new Error(`scanline size ${raw.length} != ${expected}: ${filePath}`)
  if (raw[0] !== 0) throw new Error(`first scanline filter byte != 0: ${filePath}`)
}

// ---- Slug source ------------------------------------------------------------

async function fetchSlugs(): Promise<{ slugs: string[]; source: "api" | "seed" }> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 4000)
    const token = blogApiToken()
    const res = await fetch(BLOG_API_URL, {
      signal: controller.signal,
      ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
    })
    clearTimeout(timeout)
    if (!res.ok) return { slugs: [], source: "seed" }
    const data: unknown = await res.json()
    const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items
    if (!Array.isArray(items)) return { slugs: [], source: "seed" }
    const slugs = items
      .filter(
        (p): p is Record<string, unknown> =>
          typeof p === "object" && p !== null && typeof (p as Record<string, unknown>).slug === "string"
      )
      .map((p) => String(p.slug))
      .filter((s) => /^[a-z0-9-]+$/.test(s))
    if (slugs.length === 0) return { slugs: [], source: "seed" }
    return { slugs, source: "api" }
  } catch {
    return { slugs: [], source: "seed" }
  }
}

// ---- Main -------------------------------------------------------------------

async function main(): Promise<void> {
  const { slugs, source } = await fetchSlugs()
  const use = slugs.length > 0 ? slugs : SEED_SLUGS
  const usedSource = slugs.length > 0 ? source : "seed"

  mkdirSync(OUT_DIR, { recursive: true })

  const titleColor: [number, number, number, number] = [226, 232, 240, 255]
  const wordmarkColor: [number, number, number, number] = [255, 255, 255, 255]
  const ruleColor: [number, number, number, number] = [148, 163, 184, 110]
  const footerColor: [number, number, number, number] = [148, 163, 184, 215]

  let count = 0
  for (const slug of use) {
    const [top, bottom] = GRADIENTS[fnv1a(slug) % GRADIENTS.length]
    const c = makeCanvas()
    fillGradient(c.buf, top, bottom)

    // Wordmark top-left + thin accent rule underneath.
    const ww = drawText(c, "OPERION", 48, 44, 2, wordmarkColor)
    fillRect(c, 48, 44 + 14 + 8, ww + 24, 2, ruleColor)

    // Title (slug-derived, uppercase, wrapped, centered).
    renderTitle(c, titleFromSlug(slug), titleColor)

    // Footer.
    const footer = "operionerp.xyz"
    drawText(c, footer, Math.round((WIDTH - footer.length * 6 * 2) / 2), HEIGHT - 34 - 14, 2, footerColor)

    const filePath = join(OUT_DIR, `${slug}.png`)
    writeFileSync(filePath, encodePng(c.buf))
    verifyPng(filePath)
    count++
  }

  console.log(`OG images generated: ${count} (slugs from: ${usedSource})`)
}

main().catch((err) => {
  console.error("generate-og-images failed:", err)
  process.exit(1)
})
