import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

type Theme = "dark" | "light" | "system"

interface ThemeContextValue {
  theme: Theme
  resolvedTheme: "dark" | "light"
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function getSystemTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "light"
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "system"
  return (localStorage.getItem("operion-theme") as Theme) || "system"
}

function applyResolvedTheme(root: HTMLElement, resolved: "dark" | "light") {
  root.classList.remove("light", "dark")
  root.classList.add(resolved)

  let meta = document.head.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')
  if (!meta) {
    meta = document.createElement("meta")
    meta.name = "color-scheme"
    document.head.appendChild(meta)
  }
  meta.content = resolved
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme)
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">("light")

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem("operion-theme", newTheme)
  }

  useEffect(() => {
    const root = document.documentElement

    const resolved = theme === "system" ? getSystemTheme() : theme
    applyResolvedTheme(root, resolved)
    setResolvedTheme(resolved)

    if (theme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)")
      const handler = (e: MediaQueryListEvent) => {
        const sys = e.matches ? "dark" : "light"
        applyResolvedTheme(root, sys)
        setResolvedTheme(sys)
      }
      mq.addEventListener("change", handler)
      return () => mq.removeEventListener("change", handler)
    }
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider")
  return ctx
}
