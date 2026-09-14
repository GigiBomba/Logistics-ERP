import { Component, type ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { TriangleAlert } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
}

class WidgetErrorBoundaryInner extends Component<Props & { t: (key: string) => string }, State> {
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
                {this.props.t("errorBoundary.loadingSection")}
              </p>
            </CardContent>
          </Card>
        )
      )
    }

    return this.props.children
  }
}

export function WidgetErrorBoundary({ children, fallback }: Props) {
  const { t } = useLocale()
  return <WidgetErrorBoundaryInner children={children} fallback={fallback} t={t} />
}
