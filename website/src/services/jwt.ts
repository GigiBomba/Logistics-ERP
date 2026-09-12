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

    // Restore the base64url alphabet (-/_ → +//) used by JWT encoders.
    let payload = parts[1].replace(/-/g, "+").replace(/_/g, "/")

    // Restore base64 padding that was stripped by the JWT encoder, but only
    // when the payload doesn't already end with the required padding. This
    // avoids double-padding malformed input (e.g. "...p===="), which atob
    // rejects. Valid tokens remain byte-identical.
    const padding = 4 - (payload.length % 4)
    if (padding !== 4 && !payload.endsWith("=".repeat(padding))) {
      payload += "=".repeat(padding)
    }

    const decoded = JSON.parse(atob(payload))
    return typeof decoded === "object" && decoded !== null ? decoded : null
  } catch {
    return null
  }
}
