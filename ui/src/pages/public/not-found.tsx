import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Link } from "react-router-dom"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Button } from "@/components/ui/button"
import { FileQuestion, Home, Phone } from "lucide-react"

export default function NotFoundPage() {
  return (
    <>
      <Helmet>
        <title>Page Not Found - Operion ERP</title>
      </Helmet>

      <SectionWrapper className="flex min-h-[calc(100vh-16rem)] items-center justify-center">
        <div className="mx-auto max-w-md text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10">
              <FileQuestion className="h-10 w-10 text-primary" />
            </div>
          </motion.div>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="mt-6 text-7xl font-extrabold tracking-tight text-foreground"
          >
            404
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="mt-4 text-2xl font-bold tracking-tight text-foreground"
          >
            Page not found
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="mt-3 text-base text-muted-foreground"
          >
            The page you're looking for doesn't exist or has been moved.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row"
          >
            <Button asChild>
              <Link to="/">
                <Home className="mr-2 h-4 w-4" />
                Go Home
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/contact">
                <Phone className="mr-2 h-4 w-4" />
                Contact Support
              </Link>
            </Button>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
