import { createServer } from 'node:http'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, 'dist')
const port = 8080

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
  let path = join(root, req.url === '/' ? 'index.html' : req.url)
  if (!existsSync(path)) path = join(root, 'index.html')
  const ext = extname(path)
  const content = readFileSync(path)
  res.writeHead(200, { 'Content-Type': mime[ext] || 'application/octet-stream' })
  res.end(content)
}).listen(port, () => {
  console.log(`Server running on http://localhost:${port}`)
})
