import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { HelmetProvider } from "react-helmet-async"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { ErrorBoundary } from "react-error-boundary"
import { ThemeProvider } from "@/contexts/theme-provider"
import { LocaleProvider, useLocale } from "@/i18n/locale-context"
import { AuthProvider } from "@/contexts/auth-provider"
import { Button } from "@/components/ui/button"
import { trackError } from "@/services/analytics"
import { registerServiceWorker } from "@/lib/sw-register"
import App from "@/App"
import "@/styles/globals.css"

registerServiceWorker()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Fatal error digest captured by onError and surfaced via the "Report this issue" action.
let lastErrorDigest = ""

function buildReportDigest(error: unknown, componentStack: string): string {
  const message =
    error instanceof Error ? `${error.message}\n\n${error.stack ?? ""}` : String(error)
  return encodeURIComponent(`[Fatal UI Error]\n\n${message}\n\nComponent stack:\n${componentStack}`.slice(0, 4000))
}

function ErrorFallback({ error, resetErrorBoundary }: { error: unknown; resetErrorBoundary: () => void }) {
  const { t } = useLocale()
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold text-destructive">{t("errorBoundary.title")}</h1>
        <p className="mt-2 text-muted-foreground">
          {error instanceof Error ? error.message : t("errorBoundary.unexpected")}
        </p>
        <div className="mt-4 flex items-center justify-center gap-2">
          <Button onClick={resetErrorBoundary}>{t("errorBoundary.tryAgain")}</Button>
          <Button variant="outline" asChild>
            {/* Opens the in-app support flow with the error digest attached (public users get
                redirected to login via ProtectedRoute). */}
            <a href={`/dashboard/support?report=1&error=${lastErrorDigest}`}>
              {t("errorBoundary.report")}
            </a>
          </Button>
        </div>
      </div>
    </div>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* LocaleProvider stays outside the boundary so the fallback UI can use t() with
        raw-key fallback for keys that are not yet present in the locale JSON. */}
    <LocaleProvider>
      <ErrorBoundary
        FallbackComponent={ErrorFallback}
        onError={(error, info) => {
          lastErrorDigest = buildReportDigest(error, info.componentStack ?? "")
          trackError(error instanceof Error ? error : new Error(String(error)), {
            componentStack: info.componentStack ?? "",
            fatal: "true",
          })
        }}
      >
        <HelmetProvider>
          <QueryClientProvider client={queryClient}>
            <ThemeProvider>
              <AuthProvider>
                <App />
                <Toaster position="bottom-right" richColors closeButton />
              </AuthProvider>
            </ThemeProvider>
          </QueryClientProvider>
        </HelmetProvider>
      </ErrorBoundary>
    </LocaleProvider>
  </StrictMode>
)
