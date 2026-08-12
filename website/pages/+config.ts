import vikeReact from "vike-react/config"
import type { Config } from "vike/types"

export default {
  extends: vikeReact,
  prerender: true,
  // Self-hosted webfonts (Inter / JetBrains Mono) — see scripts/fetch-fonts.mjs.
  // The root index.html link is not part of vike's output, so declare it here;
  // it is injected into <head> of every prerendered page + the SPA shell.
  headHtmlBegin: '<link rel="stylesheet" href="/fonts/fonts.css" />',
} satisfies Config
