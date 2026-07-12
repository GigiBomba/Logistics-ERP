import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"

export default function NotFoundPage() {
  return (
    <SectionWrapper className="flex flex-1 items-center justify-center">
      <EmptyState
        title="Page not found"
        description="The page you're looking for doesn't exist or has been moved."
        action={{ label: "Go home", onClick: () => (window.location.href = "/") }}
      />
    </SectionWrapper>
  )
}
