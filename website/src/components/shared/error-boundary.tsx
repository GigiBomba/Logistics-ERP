import { Component, type ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { TriangleAlert } from "lucide-react"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
}

export class WidgetErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <Card className="border-destructive/30 bg-destructive/5">
            <CardContent className="flex items-center gap-3 p-4">
              <TriangleAlert className="h-5 w-5 text-destructive" />
              <p className="text-sm text-muted-foreground">
                Something went wrong loading this section.
              </p>
            </CardContent>
          </Card>
        )
      )
    }

    return this.props.children
  }
}
