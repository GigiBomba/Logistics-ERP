"use client"

import { useEffect, useState, useCallback } from "react"
import { cn } from "@/lib/utils"

interface TableOfContentsItem {
  id: string
  text: string
  level: 2 | 3
}

interface TableOfContentsProps {
  headings?: TableOfContentsItem[]
  className?: string
}

export function TableOfContents({ headings, className }: TableOfContentsProps) {
  const [activeId, setActiveId] = useState<string>("")
  const [items, setItems] = useState<TableOfContentsItem[]>(headings ?? [])

  const updateActiveHeading = useCallback((entries: IntersectionObserverEntry[]) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        setActiveId(entry.target.id)
      }
    }
  }, [])

  useEffect(() => {
    if (headings) {
      setItems(headings)
      return
    }

    const article = document.querySelector<HTMLElement>("article")
    if (!article) return

    const headingElements = article.querySelectorAll<HTMLHeadingElement>("h2, h3")
    const extracted: TableOfContentsItem[] = []

    headingElements.forEach((el) => {
      const id = el.id || (el.textContent?.toLowerCase().replace(/\s+/g, "-") ?? "")
      if (!el.id) el.id = id
      extracted.push({
        id,
        text: el.textContent ?? "",
        level: el.tagName === "H2" ? 2 : 3,
      })
    })

    setItems(extracted)
  }, [headings])

  useEffect(() => {
    if (items.length === 0) return

    const elements = items
      .map((item) => document.getElementById(item.id))
      .filter((el): el is HTMLElement => el !== null)

    if (elements.length === 0) return

    const observer = new IntersectionObserver(updateActiveHeading, {
      rootMargin: "-80px 0px -60% 0px",
      threshold: 0,
    })

    elements.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [items, updateActiveHeading])

  if (items.length === 0) return null

  return (
    <nav className={cn("sticky top-24 max-h-[calc(100vh-8rem)] overflow-auto", className)}>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        On this page
      </h3>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              onClick={(e) => {
                e.preventDefault()
                document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth" })
              }}
              className={cn(
                "block text-sm transition-colors hover:text-foreground",
                item.level === 3 ? "pl-4" : "pl-0",
                activeId === item.id
                  ? "font-medium text-foreground"
                  : "text-muted-foreground"
              )}
            >
              {item.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
