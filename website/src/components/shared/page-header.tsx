import { cn } from "@/lib/utils"

interface PageHeaderProps {
  title: string
  description?: string
  children?: React.ReactNode
  className?: string
}

export function PageHeader({ title, description, children, className }: PageHeaderProps) {
  return (
    <div className={cn("py-12 md:py-16", className)}>
      <div className="container-wide">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{title}</h1>
        {description && (
          <p className="mt-4 max-w-2xl text-lg text-foreground/80">{description}</p>
        )}
        {children}
      </div>
    </div>
  )
}

interface SectionHeaderProps {
  title: string
  description?: string
  className?: string
}

export function SectionHeader({ title, description, className }: SectionHeaderProps) {
  return (
    <div className={cn("mx-auto max-w-2xl text-center", className)}>
      <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h2>
      {description && <p className="mt-4 text-foreground/80">{description}</p>}
    </div>
  )
}
