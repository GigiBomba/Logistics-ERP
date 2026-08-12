import { cn } from "@/lib/utils"

interface LogoCloudLogo {
  name: string
  src: string
  href?: string
}

interface LogoCloudProps {
  logos: LogoCloudLogo[]
  title?: string
  className?: string
}

export function LogoCloud({ logos, title, className }: LogoCloudProps) {
  return (
    <div className={cn("py-12", className)}>
      {title && (
        <p className="mb-8 text-center text-sm font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </p>
      )}
      <div className="mx-auto grid max-w-5xl grid-cols-2 items-center gap-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {logos.map((logo) => {
          const content = (
            <img
              loading="lazy"
              src={logo.src}
              alt={`${logo.name} logo`}
              className={cn(
                "mx-auto max-h-10 w-auto object-contain",
                "opacity-50 grayscale transition-all duration-300",
                "hover:opacity-100 hover:grayscale-0"
              )}
            />
          )

          return (
            <div key={logo.name} className="flex items-center justify-center">
              {logo.href ? (
                <a
                  href={logo.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block"
                >
                  {content}
                </a>
              ) : (
                content
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
