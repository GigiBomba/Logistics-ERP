import * as React from "react"
import { cn } from "@/lib/utils"

const sizeClasses = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-14 w-14",
}

const fontSizeClasses = {
  sm: "text-xs",
  md: "text-sm",
  lg: "text-lg",
}

interface AvatarContextValue {
  size: keyof typeof sizeClasses
}

const AvatarContext = React.createContext<AvatarContextValue>({ size: "md" })

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: keyof typeof sizeClasses
}

export function Avatar({ className, size = "md", ...props }: AvatarProps) {
  return (
    <AvatarContext.Provider value={{ size }}>
      <div
        className={cn(
          "relative flex shrink-0 overflow-hidden rounded-full",
          sizeClasses[size],
          className
        )}
        {...props}
      />
    </AvatarContext.Provider>
  )
}

export interface AvatarImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {}

export function AvatarImage({ className, ...props }: AvatarImageProps) {
  const [hasError, setHasError] = React.useState(false)

  if (hasError) return null

  return (
    <img
      loading="lazy"
      className={cn("aspect-square h-full w-full object-cover", className)}
      onError={() => setHasError(true)}
      {...props}
    />
  )
}

export interface AvatarFallbackProps extends React.HTMLAttributes<HTMLDivElement> {}

export function AvatarFallback({ className, ...props }: AvatarFallbackProps) {
  const { size } = React.useContext(AvatarContext)

  return (
    <div
      className={cn(
        "flex h-full w-full items-center justify-center rounded-full bg-muted font-medium text-muted-foreground",
        fontSizeClasses[size],
        className
      )}
      {...props}
    />
  )
}
