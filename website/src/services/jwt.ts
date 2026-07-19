/**
 * Client-side JWT payload decoding (no signature verification).
 *
 * ⚠ Signature verification is intentionally skipped — the server always
 * verifies the signature on protected endpoints.  Client-side claims are
 * only used for UI gating (show/hide admin panels), mirroring the desktop
 * app approach (Calculator logistica/client/auth.py).
 */

export interface JwtClaims {
  sub?: string
  role?: string
  is_admin?: boolean
  company_id?: number
  [key: string]: unknown
}

export function verifyJwt(token: string): JwtClaims | null {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) {
      return null
    }

    let payload = parts[1].replace(/-/g, "+").replace(/_/g, "/")

    // Restore base64 padding that was stripped by the JWT encoder
    const padding = 4 - (payload.length % 4)
    if (padding !== 4) {
      payload += "=".repeat(padding)
    }

    const decoded = JSON.parse(atob(payload))
    return typeof decoded === "object" && decoded !== null ? decoded : null
  } catch {
    return null
  }
}
