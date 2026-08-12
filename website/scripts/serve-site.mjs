#!/usr/bin/env node
/**
 * Production static server for the Operion website (cloudflare-tunnel origin).
 *
 * Hosting model: everything runs on the operator's PC; operionerp.xyz reaches
 * this machine through a cloudflared tunnel whose ingress maps
 * `operionerp.xyz -> http://127.0.0.1:8080` (remote-managed tunnel config).
 * This server is the origin for that route:
 *   - serves the vike build output (dist/client, prerendered pages + assets)
 *   - applies the security headers from public/_headers (Cloudflare syntax)
 *   - SPA fallback: unknown paths serve dist/client/index.html (mirrors
 *     public/_redirects `/* /index.html 200`)
 *
 * Usage:  PORT=8080 node scripts/serve-site.mjs
 * (bind host is 127.0.0.1 — the tunnel connects locally)
 */
import { createServer } from "node:http"
import { readFile, stat } from "node:fs/promises"
import { join, extname, normalize, sep } from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("../dist/client", import.meta.url))
const headersFile = fileURLToPath(new URL("../public/_headers", import.meta.url))
const port = Number(process.env.PORT || 8080)
const host = process.env.HOST || "127.0.0.1"

const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
  ".json": "application/json", ".xml": "application/xml", ".txt": "text/plain",
  ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
  ".webmanifest": "application/manifest+json", ".map": "application/json",
}

// Parse public/_headers (Cloudflare Pages syntax):
//   /*
//     Header: value
//   /blog/*
//     Cache-Control: max-age=60
function parseHeadersFile(text) {
  const sections = []
  let current = null
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd()
    if (!line.trim() || line.trimStart().startsWith("#")) continue
    if (!/^\s/.test(raw)) {
      current = { pattern: line.trim(), headers: [] }
      sections.push(current)
    } else if (current) {
      const m = line.trim().match(/^([\w-]+)\s*(?::|=)\s*(.*)$/)
      if (m) current.headers.push([m[1], m[2]])
    }
  }
  return sections.map((s) => ({
    re: new RegExp("^" + s.pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$"),
    headers: s.headers,
  }))
}

function safeJoin(base, pathname) {
  const resolved = normalize(join(base, pathname))
  return resolved.startsWith(normalize(base) + sep) || resolved === normalize(base) ? resolved : base
}

const headersRules = await readFile(headersFile, "utf8").then(parseHeadersFile).catch(() => [])

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${host}:${port}`)
    const pathname = decodeURIComponent(url.pathname)
    let filePath = safeJoin(root, pathname)
    let info = await stat(filePath).catch(() => null)

    if (info && info.isDirectory()) {
      const idx = join(filePath, "index.html")
      info = await stat(idx).catch(() => null)
      if (info && info.isFile()) filePath = idx
      else filePath = join(root, "index.html")
    } else if (!info || !info.isFile()) {
      // SPA fallback — mirrors public/_redirects: /* /index.html 200
      filePath = join(root, "index.html")
    }

    const content = await readFile(filePath)
    const type = MIME[extname(filePath).toLowerCase()] || "application/octet-stream"
    const headers = { "Content-Type": `${type}; charset=utf-8` }
    for (const rule of headersRules) {
      if (rule.re.test(pathname)) {
        for (const [name, value] of rule.headers) headers[name] = value
      }
    }
    res.writeHead(200, headers)
    res.end(content)
  } catch (err) {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" })
    res.end(`operion-site error: ${err.message}`)
  }
})

server.listen(port, host, () =>
  console.log(`[operion-site] serving dist/client on http://${host}:${port} (tunnel origin)`),
)
