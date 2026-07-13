import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"

export interface PaginationProps extends React.HTMLAttributes<HTMLElement> {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  siblingCount?: number
}

function getPageNumbers(current: number, total: number, siblingCount: number): (number | "ellipsis")[] {
  const totalNumbers = siblingCount * 2 + 5 // siblings + first + last + current + 2 ellipsis slots
  const totalSlots = totalNumbers + 2 // account for ellipsis

  if (total <= totalSlots) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const leftSiblingIndex = Math.max(current - siblingCount, 1)
  const rightSiblingIndex = Math.min(current + siblingCount, total)

  const showLeftEllipsis = leftSiblingIndex > 2
  const showRightEllipsis = rightSiblingIndex < total - 1

  if (!showLeftEllipsis && showRightEllipsis) {
    const leftItemCount = 3 + 2 * siblingCount
    const leftRange = Array.from({ length: leftItemCount }, (_, i) => i + 1)
    return [...leftRange, "ellipsis", total]
  }

  if (showLeftEllipsis && !showRightEllipsis) {
    const rightItemCount = 3 + 2 * siblingCount
    const rightRange = Array.from({ length: rightItemCount }, (_, i) => total - rightItemCount + i + 1)
    return [1, "ellipsis", ...rightRange]
  }

  const middleRange = Array.from({ length: rightSiblingIndex - leftSiblingIndex + 1 }, (_, i) => leftSiblingIndex + i)
  return [1, "ellipsis", ...middleRange, "ellipsis", total]
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  siblingCount = 1,
  className,
  ...props
}: PaginationProps) {
  const { t } = useLocale()
  const pages = getPageNumbers(currentPage, totalPages, siblingCount)

  return (
    <nav aria-label="Pagination" className={cn("", className)} {...props}>
      <ul className="flex items-center gap-1">
        <li>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Go to previous page"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only sm:ml-1">{t("common.back")}</span>
          </Button>
        </li>

        {pages.map((page, index) =>
          page === "ellipsis" ? (
            <li key={`ellipsis-${index}`}>
              <span className="flex h-9 w-9 items-center justify-center text-muted-foreground">
                <MoreHorizontal className="h-4 w-4" />
              </span>
            </li>
          ) : (
            <li key={page}>
              <Button
                variant={currentPage === page ? "default" : "outline"}
                size="sm"
                onClick={() => onPageChange(page)}
                className={cn(
                  currentPage === page && "pointer-events-none",
                  "min-w-[2.25rem]"
                )}
                aria-label={`Go to page ${page}`}
                aria-current={currentPage === page ? "page" : undefined}
              >
                {page}
              </Button>
            </li>
          )
        )}

        <li>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            aria-label="Go to next page"
          >
            <span className="sr-only sm:not-sr-only sm:mr-1">{t("common.next")}</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </li>
      </ul>
    </nav>
  )
}
