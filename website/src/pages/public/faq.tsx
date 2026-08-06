import { useState, useMemo } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { Link } from "react-router"
import { motion, AnimatePresence } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { ChevronDown, Search, MessageCircle } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { SearchInput } from "@/components/shared/search-input"
import { cn } from "@/lib/utils"
import { JsonLd, faqSchema } from "@/components/seo/structured-data"

export default function FaqPage() {
  const { t } = useLocale()
  const [openItems, setOpenItems] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState("")

  const categories = useMemo(() => [
    {
      id: "general",
      title: t("faq.general"),
      items: [
        { q: t("faq.general1.q"), a: t("faq.general1.a") },
        { q: t("faq.general2.q"), a: t("faq.general2.a") },
        { q: t("faq.general3.q"), a: t("faq.general3.a") },
        { q: t("faq.general4.q"), a: t("faq.general4.a") },
      ],
    },
    {
      id: "billing",
      title: t("faq.billing"),
      items: [
        { q: t("faq.billing1.q"), a: t("faq.billing1.a") },
        { q: t("faq.billing2.q"), a: t("faq.billing2.a") },
        { q: t("faq.billing3.q"), a: t("faq.billing3.a") },
        { q: t("faq.billing4.q"), a: t("faq.billing4.a") },
        { q: t("faq.billing5.q"), a: t("faq.billing5.a") },
      ],
    },
    {
      id: "technical",
      title: t("faq.technical"),
      items: [
        { q: t("faq.technical1.q"), a: t("faq.technical1.a") },
        { q: t("faq.technical2.q"), a: t("faq.technical2.a") },
        { q: t("faq.technical3.q"), a: t("faq.technical3.a") },
        { q: t("faq.technical4.q"), a: t("faq.technical4.a") },
        { q: t("faq.technical5.q"), a: t("faq.technical5.a") },
      ],
    },
    {
      id: "security",
      title: t("faq.security"),
      items: [
        { q: t("faq.security1.q"), a: t("faq.security1.a") },
        { q: t("faq.security2.q"), a: t("faq.security2.a") },
        { q: t("faq.security3.q"), a: t("faq.security3.a") },
        { q: t("faq.security4.q"), a: t("faq.security4.a") },
        { q: t("faq.security5.q"), a: t("faq.security5.a") },
      ],
    },
  ], [t])

  const allFaqItems = useMemo(() =>
    categories.flatMap((cat) =>
      cat.items.map((item) => ({ question: item.q, answer: item.a }))
    ),
    [categories]
  )

  function toggle(itemKey: string) {
    setOpenItems((prev) =>
      prev.includes(itemKey) ? prev.filter((k) => k !== itemKey) : [...prev, itemKey]
    )
  }

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return categories

    const query = searchQuery.toLowerCase().trim()
    return categories
      .map((cat) => ({
        ...cat,
        items: cat.items.filter(
          (item) =>
            item.q.toLowerCase().includes(query) ||
            item.a.toLowerCase().includes(query)
        ),
      }))
      .filter((cat) => cat.items.length > 0)
  }, [searchQuery, categories])

  return (
    <>
      <SeoHead
        title={t("faq.meta.title")}
        description={t("faq.meta.description")}
        canonical="https://operionerp.xyz/faq"
      />
      <JsonLd data={faqSchema(allFaqItems)} />
      <PageHeader title={t("faq.title")} description={t("faq.subtitle")} />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Search */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-10"
          >
            <SearchInput
              placeholder={t("faq.searchPlaceholder")}
              value={searchQuery}
              onChange={setSearchQuery}
              className="max-w-xl mx-auto"
            />
          </motion.div>

          {/* Category Tabs + Content */}
          <Tabs defaultValue="general">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="flex justify-center mb-8"
            >
              <TabsList>
                {categories.map((cat) => (
                  <TabsTrigger key={cat.id} value={cat.id}>
                    {cat.title}
                  </TabsTrigger>
                ))}
              </TabsList>
            </motion.div>

            {categories.map((category) => {
              const activeItems = searchQuery.trim()
                ? filteredCategories.find((c) => c.id === category.id)?.items ?? []
                : category.items

              return (
                <TabsContent key={category.id} value={category.id}>
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="flex items-center gap-3 mb-4">
                      <h2 className="text-xl font-bold">{category.title}</h2>
                      <Badge variant="secondary">{activeItems.length}</Badge>
                    </div>
                    {activeItems.length > 0 ? (
                      <div className="space-y-3">
                        {activeItems.map((item) => {
                          const key = `${category.title}-${item.q}`
                          const isOpen = openItems.includes(key)
                          return (
                            <Card
                              key={key}
                              className="cursor-pointer transition-shadow hover:shadow-sm"
                              onClick={() => toggle(key)}
                            >
                              <div className="flex items-center justify-between p-5">
                                <h3 className="pr-4 text-sm font-medium">{item.q}</h3>
                                <ChevronDown
                                  className={cn(
                                    "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
                                    isOpen && "rotate-180"
                                  )}
                                />
                              </div>
                              <AnimatePresence>
                                {isOpen && (
                                  <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="overflow-hidden"
                                  >
                                    <p className="px-5 pb-5 text-sm text-foreground/80">{item.a}</p>
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </Card>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center py-12 text-center">
                        <Search className="h-8 w-8 text-muted-foreground/50 mb-3" />
                        <p className="text-sm text-muted-foreground">
                          {t("faq.noResults")}
                        </p>
                      </div>
                    )}
                  </motion.div>
                </TabsContent>
              )
            })}
          </Tabs>

          {/* Still have questions? */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-16 text-center"
          >
            <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-primary/5 to-background">
              <div className="p-8">
                <div className="flex justify-center mb-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                    <MessageCircle className="h-6 w-6 text-primary" />
                  </div>
                </div>
                <h2 className="text-2xl font-bold tracking-tight">{t("faq.stillQuestions")}</h2>
                <p className="mt-2 text-muted-foreground max-w-md mx-auto">
                  {t("faq.supportText")}
                </p>
                <Button size="lg" className="mt-6" asChild>
                  <Link to="/contact">
                    <MessageCircle className="mr-2 h-4 w-4" />
                    {t("faq.contactSupport")}
                  </Link>
                </Button>
              </div>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
