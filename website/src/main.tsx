import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { HelmetProvider } from "react-helmet-async"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { ErrorBoundary } from "react-error-boundary"
import { ThemeProvider } from "@/contexts/theme-provider"
import { LocaleProvider } from "@/i18n/locale-context"
import { AuthProvider } from "@/contexts/auth-provider"
import App from "@/App"
import "@/styles/globals.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function ErrorFallback({ error, resetErrorBoundary }: { error: unknown; resetErrorBoundary: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold text-destructive">Something went wrong</h1>
        <p className="mt-2 text-muted-foreground">{error instanceof Error ? error.message : "An unexpected error occurred"}</p>
        <button
          onClick={resetErrorBoundary}
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Try again
        </button>
      </div>
    </div>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider>
            <LocaleProvider>
              <AuthProvider>
                <App />
                <Toaster position="bottom-right" richColors closeButton />
              </AuthProvider>
            </LocaleProvider>
          </ThemeProvider>
        </QueryClientProvider>
      </HelmetProvider>
    </ErrorBoundary>
  </StrictMode>
)
