#!/usr/bin/env node
/**
 * SPA-fallback static preview server for Playwright e2e (owned by the e2e lane).
 *
 * `vite preview` serves the built `dist/client` exactly as-is, which 404s every
 * non-prerendered route (/login, /register, /docs, /dashboard/*, /admin/*, ...).
 * In production the app is served by Cloudflare Pages, whose public/_redirects
 * file applies the SPA fallback `/*  /index.html  200`. This tiny server
 * replicates that behaviour so the e2e critical tier can exercise the dynamic
 * routes against a production build (deterministic — no dev-server compilation).
 *
 * Usage:  PORT=3000 node e2e/serve-preview.mjs
 */
import { createServer } from "node:http"
import { readFile, stat } from "node:fs/promises"
import { join, extname, normalize, sep } from "node:path"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("../dist/client", import.meta.url))
const port = Number(process.env.PORT || 3000)

const MIME = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".json": "application/json",
  ".xml": "application/xml",
  ".txt": "text/plain",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".webmanifest": "application/manifest+json",
  ".map": "application/json",
}

function safeJoin(base, pathname) {
  const resolved = normalize(join(base, pathname))
  return resolved.startsWith(normalize(base) + sep) || resolved === normalize(base) ? resolved : base
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://localhost:${port}`)
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
    res.writeHead(200, { "Content-Type": `${type}; charset=utf-8`, "Cache-Control": "no-store" })
    res.end(content)
  } catch (err) {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" })
    res.end(`e2e-preview error: ${err.message}`)
  }
})

server.listen(port, () => console.log(`[e2e-preview] serving dist/client with SPA fallback on :${port}`))
