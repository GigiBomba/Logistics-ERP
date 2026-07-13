import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useNavigate, useParams, Link } from "react-router"
import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { motion, AnimatePresence } from "motion/react"
import {
  FileText,
  Eye,
  Save,
  Send,
  Trash2,
  TagIcon,
  ImageIcon,
  Search,
  AlertTriangle,
  Loader2,
  ArrowLeft,
  PenLine,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input, Label, Textarea } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Tag } from "@/components/ui/tag"
import { Callout } from "@/components/ui/callout"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Skeleton } from "@/components/ui/loading-spinner"
// TODO: Implement when backend endpoint is ready
// import {
//   useCreateBlogPost,
//   useUpdateBlogPost,
//   useDeleteBlogPost,
//   useBlogPost,
//   useBlogCategories,
// } from "@/services/queries"
import { useAuth } from "@/contexts/auth-provider"
import { useLocale } from "@/i18n/locale-context"

const blogSchema = z.object({
  title: z.string().min(5, "Title must be at least 5 characters"),
  slug: z.string().min(1, "Slug is required"),
  excerpt: z.string().min(20, "Excerpt must be at least 20 characters"),
  content: z.string().min(1, "Content is required"),
  category_id: z.string().min(1, "Category is required"),
  tags: z.string().optional(),
  featured_image: z.string().optional(),
  seo_title: z.string().optional(),
  seo_description: z.string().optional(),
  published: z.boolean(),
})

type BlogForm = z.infer<typeof blogSchema>

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
}

function renderMarkdown(md: string): string {
  let html = md
    .replace(/^### (.*$)/gim, "<h3 class=\"text-lg font-semibold mt-4 mb-2\">$1</h3>")
    .replace(/^## (.*$)/gim, "<h2 class=\"text-xl font-bold mt-5 mb-3\">$1</h2>")
    .replace(/^# (.*$)/gim, "<h1 class=\"text-2xl font-bold mt-6 mb-4\">$1</h1>")
    .replace(/\*\*\*(.*?)\*\*\*/gim, "<em><strong>$1</strong></em>")
    .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/gim, "<em>$1</em>")
    .replace(/`([^`]+)`/gim, "<code class=\"rounded bg-muted px-1 py-0.5 text-sm font-mono\">$1</code>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" class="text-primary underline underline-offset-2" target="_blank" rel="noopener">$1</a>')

  // Sanitize: strip javascript: URLs and dangerous attributes from <a> tags
  html = html.replace(/<a\s+href="javascript:[^"]*"[^>]*>/gi, '<a href="#" class="text-destructive">')
  // Strip onclick, onerror, onload, onmouseover and other event handlers from any tag
  html = html.replace(/\s+on\w+=["'][^"']*["']/gi, "")

  const lines = html.split("\n")
  const result: string[] = []
  let inList = false
  let listType: "ul" | "ol" | null = null

  for (const line of lines) {
    const ulMatch = line.match(/^\s*[-*]\s+(.*)/)
    const olMatch = line.match(/^\s*\d+\.\s+(.*)/)

    if (ulMatch) {
      if (!inList || listType !== "ul") {
        if (inList) result.push(`</${listType}>`)
        result.push("<ul class=\"list-disc pl-5 space-y-1 my-3\">")
        inList = true
        listType = "ul"
      }
      result.push(`<li>${ulMatch[1]}</li>`)
    } else if (olMatch) {
      if (!inList || listType !== "ol") {
        if (inList) result.push(`</${listType}>`)
        result.push("<ol class=\"list-decimal pl-5 space-y-1 my-3\">")
        inList = true
        listType = "ol"
      }
      result.push(`<li>${olMatch[1]}</li>`)
    } else {
      if (inList) {
        result.push(`</${listType}>`)
        inList = false
        listType = null
      }
      if (line.trim() === "") {
        result.push("<br/>")
      } else if (!line.startsWith("<h") && !line.startsWith("<code")) {
        result.push(`<p class="leading-relaxed my-2">${line}</p>`)
      } else {
        result.push(line)
      }
    }
  }

  if (inList && listType) {
    result.push(`</${listType}>`)
  }

  return result.join("\n")
}

export default function BlogEditorPage() {
  const { slug } = useParams<{ slug?: string }>()
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const { t } = useLocale()
  const isEditMode = !!slug

  // TODO: Implement when backend endpoint is ready
  // const { data: existingPost, isLoading: postLoading } = useBlogPost(slug || "")
  // const { data: categories, isLoading: categoriesLoading } = useBlogCategories()
  //
  // const createPost = useCreateBlogPost()
  // const updatePost = useUpdateBlogPost()
  // const deletePost = useDeleteBlogPost()

  const existingPost = undefined as { title: string; slug: string; excerpt: string; content: string; category_id: string; tags?: string[]; featured_image?: string; seo_title?: string; seo_description?: string; published_at?: string | null } | undefined
  const postLoading = false
  const categories = undefined as { id: string; name: string }[] | undefined
  const categoriesLoading = false

  const createPost = { mutate: (_payload: unknown, _options?: { onSuccess?: (res: { data: { slug: string } }) => void }) => {}, isPending: false } as const
  const updatePost = { mutate: (_payload: unknown, _options?: { onSuccess?: (res: { data: { slug: string } }) => void }) => {}, isPending: false } as const
  const deletePost = { mutate: (_slug: string, _options?: { onSuccess?: () => void }) => {}, isPending: false } as const

  const [previewTab, setPreviewTab] = useState("edit")
  const [autoSlug, setAutoSlug] = useState(true)

  const form = useForm<BlogForm>({
    resolver: zodResolver(blogSchema),
    defaultValues: {
      title: "",
      slug: "",
      excerpt: "",
      content: "",
      category_id: "",
      tags: "",
      featured_image: "",
      seo_title: "",
      seo_description: "",
      published: false,
    },
  })

  const titleValue = form.watch("title")
  const contentValue = form.watch("content")
  const tagsValue = form.watch("tags")

  useEffect(() => {
    if (isEditMode && existingPost) {
      form.reset({
        title: existingPost.title,
        slug: existingPost.slug,
        excerpt: existingPost.excerpt,
        content: existingPost.content,
        category_id: existingPost.category_id,
        tags: existingPost.tags?.join(", ") || "",
        featured_image: existingPost.featured_image || "",
        seo_title: existingPost.seo_title || "",
        seo_description: existingPost.seo_description || "",
        published: !!existingPost.published_at,
      })
      setAutoSlug(false)
    }
  }, [existingPost, isEditMode, form])

  useEffect(() => {
    if (autoSlug && titleValue) {
      form.setValue("slug", slugify(titleValue), { shouldValidate: false })
    }
  }, [titleValue, autoSlug, form])

  const parsedTags = useMemo(() => {
    if (!tagsValue) return []
    return tagsValue
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean)
  }, [tagsValue])

  function handleSave(published: boolean) {
    form.setValue("published", published)
    form.handleSubmit(onSubmit)()
  }

  function onSubmit(data: BlogForm) {
    const payload = {
      title: data.title,
      slug: data.slug,
      excerpt: data.excerpt,
      content: data.content,
      category_id: data.category_id,
      tags: parsedTags,
      featured_image: data.featured_image || undefined,
      seo_title: data.seo_title || undefined,
      seo_description: data.seo_description || undefined,
      published: data.published,
    }

    // TODO: Implement when backend endpoint is ready - navigate on success
    if (isEditMode && slug) {
      const { slug: _payloadSlug, ...updatePayload } = payload
      updatePost.mutate(
        { slug, ...updatePayload },
        {
          onSuccess: (res: { data: { slug: string } }) => {
            navigate(`/blog/${res.data.slug}`)
          },
        }
      )
    } else {
      createPost.mutate(payload, {
        onSuccess: (res: { data: { slug: string } }) => {
          navigate(`/blog/${res.data.slug}`)
        },
      })
    }
  }

  function handleDelete() {
    if (!slug) return
    if (window.confirm("Are you sure you want to delete this article? This action cannot be undone.")) {
      deletePost.mutate(slug, {
        onSuccess: () => {
          navigate("/blog")
        },
      })
    }
  }

  const isSubmitting = createPost.isPending || updatePost.isPending

  if (!isAdmin) {
    return (
      <SectionWrapper>
        <Callout variant="warning" title="Access Denied">
          You do not have permission to access this page.
        </Callout>
      </SectionWrapper>
    )
  }

  if (isEditMode && postLoading) {
    return (
      <>
        <Helmet><title>{t("blogEditor.editTitle")}</title></Helmet>
        <SectionWrapper>
          <div className="space-y-8">
            <Skeleton className="h-10 w-64" />
            <Skeleton className="h-6 w-96" />
            <div className="grid gap-8 lg:grid-cols-3">
              <div className="lg:col-span-2 space-y-6">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-32" />
                <Skeleton className="h-96" />
              </div>
              <div className="space-y-6">
                <Skeleton className="h-48" />
                <Skeleton className="h-40" />
                <Skeleton className="h-32" />
              </div>
            </div>
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{isEditMode ? t("blogEditor.editTitle") : t("blogEditor.newTitle")}</title>
      </Helmet>

      <PageHeader
        title={isEditMode ? t("blogEditor.editArticle") : t("blogEditor.newArticle")}
        description={
          isEditMode
            ? `Editing "${existingPost?.title ?? ""}"`
            : t("blogEditor.createDesc")
        }
      />

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="mb-6 flex items-center gap-3">
            <Button variant="outline" size="sm" asChild>
              <Link to="/blog">
                <ArrowLeft className="h-4 w-4" />
                {t("blogEditor.backToBlog")}
              </Link>
            </Button>
            {isEditMode && existingPost && (
              <Badge variant={existingPost.published_at ? "success" : "secondary"}>
                {existingPost.published_at ? t("blogEditor.published") : t("blogEditor.draft")}
              </Badge>
            )}
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-8 lg:grid-cols-3">
            {/* ─── Main Form ───────────────────────────────────────── */}
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardContent className="space-y-5 pt-6">
                  {/* Title */}
                  <div className="space-y-2">
                    <Label htmlFor="title">
                      {t("blogEditor.title")} <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="title"
                      placeholder={t("blogEditor.titlePlaceholder")}
                      {...form.register("title")}
                    />
                    {form.formState.errors.title && (
                      <p className="text-xs text-destructive">{form.formState.errors.title.message}</p>
                    )}
                  </div>

                  {/* Slug */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="slug">
                        {t("blogEditor.slug")} <span className="text-destructive">*</span>
                      </Label>
                      <button
                        type="button"
                        onClick={() => setAutoSlug(!autoSlug)}
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {autoSlug ? t("blogEditor.slugAuto") : t("blogEditor.slugCustom")}
                      </button>
                    </div>
                    <Input
                      id="slug"
                      placeholder={t("blogEditor.slugPlaceholder")}
                      {...form.register("slug")}
                      onChange={(e) => {
                        form.setValue("slug", e.target.value)
                        setAutoSlug(false)
                      }}
                    />
                    {form.formState.errors.slug && (
                      <p className="text-xs text-destructive">{form.formState.errors.slug.message}</p>
                    )}
                  </div>

                  {/* Excerpt */}
                  <div className="space-y-2">
                    <Label htmlFor="excerpt">
                      {t("blogEditor.excerpt")} <span className="text-destructive">*</span>
                    </Label>
                    <Textarea
                      id="excerpt"
                      rows={3}
                      placeholder={t("blogEditor.excerptPlaceholder")}
                      {...form.register("excerpt")}
                    />
                    {form.formState.errors.excerpt && (
                      <p className="text-xs text-destructive">{form.formState.errors.excerpt.message}</p>
                    )}
                  </div>

                  {/* Content with Edit/Preview Tabs */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="content">
                        {t("blogEditor.content")} <span className="text-destructive">*</span>
                      </Label>
                      <span className="text-xs text-muted-foreground">{t("blogEditor.contentHint")}</span>
                    </div>

                    <Tabs defaultValue="edit" value={previewTab} onValueChange={setPreviewTab}>
                      <TabsList>
                        <TabsTrigger value="edit">
                          <PenLine className="h-3.5 w-3.5 mr-1.5" />
                          {t("blogEditor.edit")}
                        </TabsTrigger>
                        <TabsTrigger value="preview">
                          <Eye className="h-3.5 w-3.5 mr-1.5" />
                          {t("blogEditor.preview")}
                        </TabsTrigger>
                      </TabsList>

                      <TabsContent value="edit" className="mt-2">
                        <Textarea
                          id="content"
                          rows={18}
                          className="font-mono text-sm"
                          placeholder={t("blogEditor.contentPlaceholder")}
                          {...form.register("content")}
                        />
                        {form.formState.errors.content && (
                          <p className="text-xs text-destructive mt-1">{form.formState.errors.content.message}</p>
                        )}
                      </TabsContent>

                      <TabsContent value="preview" className="mt-2">
                        <div className="min-h-[28rem] rounded-md border border-input bg-background p-5 overflow-auto">
                          {contentValue ? (
                            <div
                              className="prose prose-sm max-w-none dark:prose-invert"
                              dangerouslySetInnerHTML={{ __html: renderMarkdown(contentValue) }}
                            />
                          ) : (
                            <div className="flex h-full min-h-[24rem] flex-col items-center justify-center text-muted-foreground">
                              <Eye className="h-8 w-8 mb-3 opacity-40" />
                              <p className="text-sm">{t("blogEditor.previewEmpty")}</p>
                            </div>
                          )}
                        </div>
                      </TabsContent>
                    </Tabs>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* ─── Sidebar ───────────────────────────────────────────── */}
            <div className="space-y-6">
              {/* Publish Controls */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Send className="h-4 w-4" />
                    {t("blogEditor.publish")}
                  </CardTitle>
                  <CardDescription>{t("blogEditor.publishDesc")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Controller
                    name="published"
                    control={form.control}
                    render={({ field }) => (
                      <div className="flex items-center gap-3 rounded-lg border p-3">
                        <div className="flex-1">
                          <p className="text-sm font-medium">{field.value ? t("blogEditor.published") : t("blogEditor.draft")}</p>
                          <p className="text-xs text-muted-foreground">
                            {field.value
                              ? t("blogEditor.publishedDesc")
                              : t("blogEditor.draftDesc")}
                          </p>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={field.value}
                          onClick={() => field.onChange(!field.value)}
                          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                            field.value ? "bg-primary" : "bg-input"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow ring-0 transition duration-200 ease-in-out ${
                              field.value ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </div>
                    )}
                  />

                  <div className="flex flex-col gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={isSubmitting}
                      onClick={() => handleSave(false)}
                      className="w-full"
                    >
                      {isSubmitting && !form.getValues("published") ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      {t("blogEditor.saveDraft")}
                    </Button>
                    <Button
                      type="button"
                      disabled={isSubmitting}
                      onClick={() => handleSave(true)}
                      className="w-full"
                    >
                      {isSubmitting && form.getValues("published") ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                      {t("blogEditor.publish")}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Category */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileText className="h-4 w-4" />
                    {t("blogEditor.category")}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Label htmlFor="category">{t("blogEditor.category")} <span className="text-destructive">*</span></Label>
                    {categoriesLoading ? (
                      <Skeleton className="h-9" />
                    ) : (
                      <select
                        id="category"
                        {...form.register("category_id")}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <option value="">{t("blogEditor.categoryPlaceholder")}</option>
                        {categories?.map((cat: { id: string; name: string }) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    )}
                    {form.formState.errors.category_id && (
                      <p className="text-xs text-destructive">{form.formState.errors.category_id.message}</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Tags */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <TagIcon className="h-4 w-4" />
                    {t("blogEditor.tags")}
                  </CardTitle>
                  <CardDescription>{t("blogEditor.tagsHint")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Input
                    placeholder={t("blogEditor.tagsPlaceholder")}
                    {...form.register("tags")}
                  />
                  <AnimatePresence>
                    {parsedTags.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="flex flex-wrap gap-1.5"
                      >
                        {parsedTags.map((t) => (
                          <Tag key={t} variant="default">
                            {t}
                          </Tag>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </CardContent>
              </Card>

              {/* Featured Image */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <ImageIcon className="h-4 w-4" />
                    {t("blogEditor.featuredImage")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Input
                    placeholder={t("blogEditor.featuredImagePlaceholder")}
                    {...form.register("featured_image")}
                  />
                  {form.watch("featured_image") && (
                    <div className="overflow-hidden rounded-lg border">
                      <img
                        loading="lazy"
                        src={form.watch("featured_image")}
                        alt="Featured preview"
                        className="h-32 w-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none"
                        }}
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* SEO */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Search className="h-4 w-4" />
                    {t("blogEditor.seo")}
                  </CardTitle>
                  <CardDescription>{t("blogEditor.seoDesc")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="seo_title">{t("blogEditor.seoTitle")}</Label>
                    <Input
                      id="seo_title"
                      placeholder={t("blogEditor.seoTitlePlaceholder")}
                      {...form.register("seo_title")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="seo_description">{t("blogEditor.seoDescription")}</Label>
                    <Textarea
                      id="seo_description"
                      rows={3}
                      placeholder={t("blogEditor.seoDescriptionPlaceholder")}
                      {...form.register("seo_description")}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Danger Zone */}
              {isEditMode && (
                <Card className="border-destructive/20">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base text-destructive">
                      <AlertTriangle className="h-4 w-4" />
                      {t("blogEditor.dangerZone")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Button
                      type="button"
                      variant="destructive"
                      disabled={deletePost.isPending}
                      onClick={handleDelete}
                      className="w-full"
                    >
                      {deletePost.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                      {t("blogEditor.deleteArticle")}
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          </form>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
