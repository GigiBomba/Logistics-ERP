import { createServer } from 'node:http'
import { request as httpsRequest } from 'node:https'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, 'dist')
const port = 8080

const API_TARGET = 'api.operionerp.xyz'

const mime = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
}

createServer((req, res) => {
  const url = req.url?.split('?')[0] ?? '/'

  // Proxy API requests to the backend
  if (url.startsWith('/api/')) {
    const options = {
      hostname: API_TARGET,
      port: 443,
      path: req.url,
      method: req.method,
      headers: {
        ...req.headers,
        host: API_TARGET,
      },
      rejectUnauthorized: true,
    }

    const proxyReq = httpsRequest(options, (proxyRes) => {
      // Forward response headers (excluding transfer-encoding to avoid issues)
      const headers = { ...proxyRes.headers }
      delete headers['transfer-encoding']
      res.writeHead(proxyRes.statusCode || 200, headers)
      proxyRes.pipe(res)
    })

    proxyReq.on('error', (err) => {
      console.error(`API proxy error for ${req.url}:`, err.message)
      res.writeHead(502, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ detail: `API proxy error: ${err.message}` }))
    })

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      req.pipe(proxyReq)
    } else {
      proxyReq.end()
    }
    return
  }

  // Serve static files
  const requestedPath = join(root, url === '/' ? 'index.html' : url)
  const ext = extname(requestedPath)

  // Asset files must exist exactly — don't fall back to index.html for missing assets
  if (url.startsWith('/assets/') && !existsSync(requestedPath)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' })
    res.end('Not found')
    return
  }

  // SPA fallback: non-file routes → serve index.html
  const isSpaFallback = !existsSync(requestedPath)
  const path = isSpaFallback ? join(root, 'index.html') : requestedPath
  const content = readFileSync(path)
  const ct = isSpaFallback ? 'text/html' : (mime[ext] || 'application/octet-stream')
  const isText = ['.html','.js','.css','.json','.svg'].includes(ext)

  // Cache strategy:
  // - index.html: never cache — always check for fresh version
  // - /assets/* (hashed filenames): cache forever (hash changes = new content)
  const isHashedAsset = path.startsWith(join(root, 'assets')) || path.includes('/assets/')
  const cacheControl = path.endsWith('index.html')
    ? 'no-cache, no-store, must-revalidate'
    : isHashedAsset
      ? 'public, max-age=31536000, immutable'
      : 'no-cache'

  res.writeHead(200, {
    'Content-Type': isText ? ct + '; charset=utf-8' : ct,
    'Cache-Control': cacheControl,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(self)',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-site',
  })
  res.end(content)
}).listen(port, () => {
  console.log(`Server running on http://localhost:${port}`)
  console.log(`API requests proxied to https://${API_TARGET}`)
})
