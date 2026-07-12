import { motion } from "motion/react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { MailCheck, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card"

export default function VerifyEmailPage() {
  return (
    <>
      <Helmet>
        <title>Check Your Email — Operion ERP</title>
      </Helmet>

      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          {/* Back link */}
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="mb-6"
          >
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to home
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <Card>
              <CardHeader className="items-center text-center">
                {/* Logo */}
                <Link
                  to="/"
                  className="mb-6 inline-flex items-center gap-2"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <span className="text-lg font-bold">O</span>
                  </div>
                  <span className="text-xl font-bold tracking-tight">
                    Operion
                  </span>
                </Link>

                {/* Mail icon */}
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <MailCheck className="h-8 w-8 text-primary" />
                </div>

                <CardTitle>Check your email</CardTitle>
                <CardDescription className="mx-auto max-w-sm">
                  We've sent a verification link to your email address.
                  Please check your inbox and click the link to verify
                  your account.
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4">
                <p className="text-center text-sm text-muted-foreground">
                  Didn't receive the email? Check your spam folder or
                  contact support.
                </p>
              </CardContent>

              <CardFooter className="flex-col gap-3">
                <Button asChild className="w-full">
                  <Link to="/login">Go to Sign In</Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link to="/contact">Contact Support</Link>
                </Button>
              </CardFooter>
            </Card>
          </motion.div>
        </div>
      </div>
    </>
  )
}
