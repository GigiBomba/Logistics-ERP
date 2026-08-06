import { http, HttpResponse } from "msw"

const mockBackupCodes = [
  "ABCD-1234",
  "EFGH-5678",
  "IJKL-9012",
  "MNOP-3456",
  "QRST-7890",
  "UVWX-2345",
  "YZAB-6789",
  "CDEF-0123",
  "GHIJ-4567",
  "KLMN-8901",
]

export const mfaHandlers = [
  http.post("*/api/v1/auth/mfa/enroll", () => {
    return HttpResponse.json({
      secret: "JBSWY3DPEHPK3PXP",
      otpauth_uri: "otpauth://totp/Operion:test@operion.dev?secret=JBSWY3DPEHPK3PXP&issuer=Operion",
      qr_payload: "https://api.qrserver.com/v1/create-qr-code/?data=otpauth%3A%2F%2Ftotp%2FOperion%3Atest%40operion.dev",
    })
  }),

  http.post("*/api/v1/auth/mfa/confirm", () => {
    return HttpResponse.json({
      mfa_enabled: true,
      backup_codes: mockBackupCodes,
    })
  }),

  http.post("*/api/v1/auth/mfa/disable", () => {
    return HttpResponse.json({ mfa_enabled: false })
  }),

  http.get("*/api/v1/auth/me/mfa-status", () => {
    return HttpResponse.json({ mfa_enabled: false })
  }),

  http.post("*/api/v1/auth/mfa/verify", () => {
    return HttpResponse.json({
      access_token: "mfa-access-token",
      refresh_token: "mfa-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    })
  }),

  http.post("*/api/v1/auth/mfa/backup-code", () => {
    return HttpResponse.json({
      access_token: "backup-access-token",
      refresh_token: "backup-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    })
  }),
]
