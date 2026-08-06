import type { OnBeforePrerenderStartAsync } from "vike/types"
import { publicRoutes } from "@/config/sitemap"

export const onBeforePrerenderStart: OnBeforePrerenderStartAsync = async (): ReturnType<OnBeforePrerenderStartAsync> => {
  // Static public routes (shared with the sitemap generator via @/config/sitemap).
  return publicRoutes
}
