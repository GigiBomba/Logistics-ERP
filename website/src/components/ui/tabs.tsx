import * as React from "react"
import { cn } from "@/lib/utils"

interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
  values: string[]
  registerValue: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

function useTabsContext() {
  const context = React.useContext(TabsContext)
  if (!context) {
    throw new Error("Tabs compound components must be used within a <Tabs />")
  }
  return context
}

export interface TabsProps {
  defaultValue: string
  value?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
  className?: string
}

export function Tabs({ defaultValue, value, onValueChange, children, className }: TabsProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue)
  const controlled = value !== undefined
  const activeValue = controlled ? value : internalValue

  const [values, setValues] = React.useState<string[]>([])

  const handleValueChange = React.useCallback(
    (newValue: string) => {
      if (!controlled) {
        setInternalValue(newValue)
      }
      onValueChange?.(newValue)
    },
    [controlled, onValueChange]
  )

  const registerValue = React.useCallback((tabValue: string) => {
    setValues((prev) => (prev.includes(tabValue) ? prev : [...prev, tabValue]))
  }, [])

  return (
    <TabsContext.Provider value={{ value: activeValue, onValueChange: handleValueChange, values, registerValue }}>
      <div className={cn("", className)} data-orientation="horizontal">
        {children}
      </div>
    </TabsContext.Provider>
  )
}

export interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {}

export function TabsList({ className, ...props }: TabsListProps) {
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground",
        className
      )}
      {...props}
    />
  )
}

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
}

export function TabsTrigger({ className, value, ...props }: TabsTriggerProps) {
  const { value: activeValue, onValueChange, values, registerValue } = useTabsContext()
  const isActive = activeValue === value

  React.useEffect(() => {
    registerValue(value)
  }, [value, registerValue])

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>) => {
      let newIndex = values.indexOf(value)
      switch (e.key) {
        case "ArrowLeft":
          newIndex = newIndex <= 0 ? values.length - 1 : newIndex - 1
          break
        case "ArrowRight":
          newIndex = newIndex >= values.length - 1 ? 0 : newIndex + 1
          break
        case "Home":
          newIndex = 0
          break
        case "End":
          newIndex = values.length - 1
          break
        default:
          return
      }
      e.preventDefault()
      onValueChange(values[newIndex])
    },
    [value, values, onValueChange]
  )

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${value}`}
      data-state={isActive ? "active" : "inactive"}
      id={`tab-${value}`}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        isActive
          ? "bg-background text-foreground shadow"
          : "text-foreground/80 hover:bg-background/50 hover:text-foreground",
        className
      )}
      onClick={() => onValueChange(value)}
      onKeyDown={handleKeyDown}
      {...props}
    />
  )
}

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
}

export function TabsContent({ className, value, ...props }: TabsContentProps) {
  const { value: activeValue } = useTabsContext()
  const isActive = activeValue === value

  if (!isActive) return null

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${value}`}
      aria-labelledby={`tab-${value}`}
      data-state={isActive ? "active" : "inactive"}
      className={cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)}
      {...props}
    />
  )
}
