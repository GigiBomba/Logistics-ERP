import { Link } from "react-router"
import { Calendar, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn, formatDate } from "@/lib/utils"

interface BlogPost {
  title: string
  slug: string
  excerpt: string
  author_name?: string
  author_avatar?: string
  category: string
  tags: string[]
  featured_image?: string
  reading_time_minutes: number
  published_at: string
}

interface BlogCardProps {
  post: BlogPost
  className?: string
}

export function BlogCard({ post, className }: BlogCardProps) {
  return (
    <Link to={`/blog/${post.slug}`} className={cn("group block", className)}>
      <Card className="h-full overflow-hidden transition-shadow hover:shadow-md">
        {post.featured_image && (
          <div className="aspect-video w-full overflow-hidden">
            <img
              loading="lazy"
              src={post.featured_image}
              alt={post.title}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
          </div>
        )}
        <CardContent className={cn("flex flex-col gap-3", post.featured_image ? "p-5" : "p-5 pt-5")}>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{post.category}</Badge>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {post.reading_time_minutes} min read
            </span>
          </div>

          <h3 className="font-semibold leading-snug group-hover:text-primary transition-colors">
            {post.title}
          </h3>

          <p className="line-clamp-2 text-sm text-muted-foreground">{post.excerpt}</p>

          <div className="mt-auto flex items-center justify-end gap-1 pt-2 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />
            {formatDate(post.published_at)}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
