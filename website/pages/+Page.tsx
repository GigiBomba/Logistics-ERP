import SSRApp from "../src/SSRApp"
import { usePageContext } from "vike-react/usePageContext"
// The app's design system must enter vike's build graph here: vike's client
// bundle is built from the pages/ directory, NOT from src/main.tsx (the legacy
// SPA entry), so this import is what puts the compiled CSS into dist/client
// and lets vike link it from the prerendered pages.
import "@/styles/globals.css"

export default function Page() {
  const pageContext = usePageContext()
  return <SSRApp url={pageContext.urlOriginal} />
}
