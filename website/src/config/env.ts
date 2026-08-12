export const envConfig = {
  turnstileSiteKey: import.meta.env.VITE_TURNSTILE_SITE_KEY || "",
  maintenanceMode: import.meta.env.VITE_MAINTENANCE_MODE === "true",
  stripePublishableKey: import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || "",
} as const

if (import.meta.env.DEV && !envConfig.turnstileSiteKey) {
  console.warn(
    "[Turnstile] VITE_TURNSTILE_SITE_KEY is not set. " +
    "Widget will not render. Get your keys at https://dash.cloudflare.com"
  )
}

if (envConfig.maintenanceMode) {
  console.info("[Maintenance] VITE_MAINTENANCE_MODE is active — public routes will redirect to /maintenance")
}
