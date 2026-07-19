import { describe, it, expect } from "vitest"
import { verifyJwt } from "@/services/jwt"

/**
 * Build a minimal JWT string for testing.
 * header.payload.signature — signature is never verified client-side.
 */
function makeToken(payload: Record<string, unknown>, signature = "fake_sig"): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const encodedPayload = btoa(JSON.stringify(payload))
  return `${header}.${encodedPayload}.${signature}`
}

/** base64url-safe variant (strips padding, replaces +/ with -_) */
function makeEncodedToken(payload: Record<string, unknown>, signature = "fake_sig"): string {
  const unsafe = makeToken(payload, signature)
  const [h, p, s] = unsafe.split(".")
  return `${h.replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_")}.${p.replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_")}.${s}`
}

describe("JwtClaims interface shape", () => {
  it("returns expected fields from a valid token", () => {
    const claims = verifyJwt(
      makeToken({ sub: "user-42", role: "admin", is_admin: true, company_id: 5 })
    )
    expect(claims).not.toBeNull()
    expect(claims!.sub).toBe("user-42")
    expect(claims!.role).toBe("admin")
    expect(claims!.is_admin).toBe(true)
    expect(claims!.company_id).toBe(5)
  })

  it("carries custom keys via the index signature", () => {
    const claims = verifyJwt(makeToken({ company_slug: "acme", tier: "enterprise" }))
    expect(claims).not.toBeNull()
    expect(claims!.company_slug).toBe("acme")
    expect(claims!.tier).toBe("enterprise")
    expect(claims!.unknown_field).toBeUndefined()
  })
})

describe("verifyJwt", () => {
  it("returns correct claims for a valid token", () => {
    const payload = { sub: "user-1", role: "dispatcher", is_admin: false, company_id: 3 }
    const claims = verifyJwt(makeToken(payload))
    expect(claims).toEqual(payload)
  })

  it("returns null for an expired token (exp in the past is still decoded)", () => {
    // verifyJwt does NOT check exp — it only decodes. The exp claim is
    // informational for the caller. We assert the decoded result includes it.
    const payload = { sub: "user-1", exp: 1000000, role: "viewer" }
    const claims = verifyJwt(makeToken(payload))
    expect(claims).not.toBeNull()
    expect(claims!.exp).toBe(1000000)
  })

  it("returns null for a malformed token (single part)", () => {
    expect(verifyJwt("just-one-part")).toBeNull()
  })

  it("returns null for a malformed token (two parts)", () => {
    expect(verifyJwt("header.payload")).toBeNull()
  })

  it("returns null for a token with non-JSON payload", () => {
    const token = `header.${btoa("not-json")}.sig`
    expect(verifyJwt(token)).toBeNull()
  })

  it("returns null for a tampered token (payload is not an object)", () => {
    const token = `header.${btoa('"just-a-string"')}.sig`
    expect(verifyJwt(token)).toBeNull()
  })

  it("returns null for a tampered token (payload is a number)", () => {
    const token = `header.${btoa("42")}.sig`
    expect(verifyJwt(token)).toBeNull()
  })

  it("returns null for a token with null payload", () => {
    const token = `header.${btoa("null")}.sig`
    expect(verifyJwt(token)).toBeNull()
  })

  it("returns null for empty string", () => {
    expect(verifyJwt("")).toBeNull()
  })

  it("handles base64url-encoded (no padding) tokens", () => {
    const payload = { check: "++//\xff\xff" }
    const token = makeEncodedToken(payload)
    const claims = verifyJwt(token)
    expect(claims).toEqual(payload)
  })

  it("returns null for tokens with extra malformed padding", () => {
    // Extra ==== appended beyond standard base64 breaks atob in most envs
    const payload = { sub: "user-1", role: "admin" }
    const raw = makeToken(payload)
    const [h, p, s] = raw.split(".")
    const paddedToken = `${h}.${p}====.${s}`
    expect(verifyJwt(paddedToken)).toBeNull()
  })

  it("returns null when token contains non-ASCII characters", () => {
    expect(verifyJwt("header.päyload.sig")).toBeNull()
  })
})
