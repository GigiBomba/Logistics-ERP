import { SeoHead } from "@/components/seo/seo-head"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const tocItems = [
  { id: "conformance-status", title: "Conformance Status" },
  { id: "what-weve-done", title: "Accessibility Features" },
  { id: "known-limitations", title: "Known Limitations" },
  { id: "testing-approach", title: "Testing Approach" },
  { id: "contact", title: "Contact" },
]

export default function AccessibilityStatementPage() {
  return (
    <>
      <SeoHead
        title="Accessibility Statement — Operion ERP"
        description="Operion ERP accessibility statement — our commitment to making our platform accessible to all users, including those with disabilities."
        canonical="https://operionerp.xyz/accessibility-statement"
      />
      <PageHeader title="Accessibility Statement" description="Last reviewed: July 2026" />

      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          {/* Table of Contents */}
          <nav className="mb-12 rounded-lg border p-6">
            <h2 className="font-semibold mb-4">Table of Contents</h2>
            <ul className="space-y-2">
              {tocItems.map((item) => (
                <li key={item.id}>
                  <a href={`#${item.id}`} className="text-sm text-primary hover:underline">
                    {item.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Content Sections */}
          <div className="space-y-10">
            {/* Conformance Status */}
            <section id="conformance-status" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Conformance Status</h2>
              <div className="mt-3 space-y-3">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Operion is committed to ensuring digital accessibility for people with disabilities. We
                  aim to meet the{" "}
                  <a
                    href="https://www.w3.org/TR/WCAG21/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Web Content Accessibility Guidelines (WCAG) 2.1 Level AA
                  </a>{" "}
                  standard, which is widely recognized as the international benchmark for web accessibility.
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  We recognize that accessibility is an ongoing effort, and we are continuously working to
                  improve the user experience for everyone. Our website and web portal are built with
                  accessibility as a core consideration, not an afterthought.
                </p>
                <div className="mt-4">
                  <Badge variant="secondary" className="text-xs">
                    WCAG 2.1 Level AA Target
                  </Badge>
                </div>
              </div>
            </section>

            {/* What We've Done */}
            <section id="what-weve-done" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Accessibility Features</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                We have implemented the following accessibility features across our website and web portal:
              </p>
              <div className="mt-6 grid gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Keyboard Navigation</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      All interactive elements are accessible via keyboard. Users can navigate through
                      forms, menus, and controls using Tab, Enter, Escape, and arrow keys. Focus order
                      follows a logical sequence that matches the visual layout of the page.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Screen Reader Support</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      We use semantic HTML elements (headings, landmarks, lists) and ARIA attributes to
                      ensure compatibility with screen readers and assistive technologies. Interactive
                      elements include descriptive labels and accessible names.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Focus Indicators</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Visible focus indicators are provided for all interactive elements, including links,
                      buttons, and form fields. The focus ring uses high-contrast colors that are visible
                      against all background variations in both light and dark themes.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Color Contrast</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Text and interactive elements maintain a minimum contrast ratio of 4.5:1 for normal
                      text and 3:1 for large text, in accordance with WCAG 2.1 Level AA requirements. The
                      interface supports both light and dark themes without compromising readability.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Responsive & Scalable</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      The interface is fully responsive and supports browser zoom up to 200% without loss
                      of content or functionality. Text can be resized using browser settings without
                      breaking the layout.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle>Alternative Text</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      All meaningful images include descriptive alt text. Decorative images are hidden
                      from assistive technologies using empty alt attributes or ARIA roles.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* Known Limitations */}
            <section id="known-limitations" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Known Limitations</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                While we strive for full accessibility, we acknowledge the following areas that need
                improvement:
              </p>
              <ul className="mt-4 list-disc pl-6 space-y-2 text-sm leading-relaxed text-muted-foreground">
                <li>
                  <strong>Third-party embedded content:</strong> Some third-party services (such as
                  interactive maps or embedded media) may not fully comply with WCAG standards. We are
                  working with our providers to improve accessibility.
                </li>
                <li>
                  <strong>Complex data tables:</strong> Some data tables in the dashboard may not have
                  full screen reader support for complex relationships. We are gradually improving table
                  markup and providing accessible summaries.
                </li>
                <li>
                  <strong>Older browser support:</strong> Some advanced ARIA patterns may not function
                  optimally in older browsers. We recommend using the latest versions of Chrome, Firefox,
                  Safari, or Edge.
                </li>
                <li>
                  <strong>Audio and video content:</strong> We are working toward providing captions and
                  transcripts for all audio and video content. Most content currently does not include
                  these alternatives.
                </li>
              </ul>
            </section>

            {/* Testing Approach */}
            <section id="testing-approach" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Testing Approach</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Our accessibility testing process includes the following methods:
              </p>
              <ul className="mt-4 list-disc pl-6 space-y-2 text-sm leading-relaxed text-muted-foreground">
                <li>
                  <strong>Automated testing with axe-core:</strong> We integrate the axe-core
                  accessibility engine into our development pipeline and CI/CD process. Every pull request
                  is automatically scanned for accessibility violations, and issues must be resolved before
                  merging.
                </li>
                <li>
                  <strong>Manual keyboard audits:</strong> Each feature is tested manually using keyboard-only
                  navigation to verify that all interactive elements are reachable and operable without a
                  mouse.
                </li>
                <li>
                  <strong>Screen reader testing:</strong> We test with NVDA (Windows) and VoiceOver (macOS)
                  to verify screen reader compatibility for key user flows.
                </li>
                <li>
                  <strong>Contrast verification:</strong> Color combinations are verified against WCAG 2.1
                  contrast requirements using automated tools and manual inspection.
                </li>
                <li>
                  <strong>Regular reviews:</strong> Accessibility is reviewed as part of our regular
                  development cycles, and we maintain a backlog of accessibility improvements for each
                  release.
                </li>
              </ul>
            </section>

            {/* Contact */}
            <section id="contact" className="scroll-mt-20">
              <h2 className="text-lg font-semibold">Contact</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                If you encounter any accessibility barriers while using our website or web portal, please
                contact us. We will do our best to provide the information you need in an accessible format
                and address any issues promptly.
              </p>
              <div className="mt-4 rounded-lg border bg-muted/30 p-4">
                <p className="text-sm font-medium">Accessibility Contact</p>
                <a
                  href="mailto:support@operionerp.xyz"
                  className="mt-1 block text-sm text-primary hover:underline"
                >
                  support@operionerp.xyz
                </a>
                <p className="mt-2 text-sm text-muted-foreground">
                  We aim to respond to accessibility inquiries within 2 business days and resolve reported
                  issues within 10 business days where possible.
                </p>
              </div>
            </section>
          </div>
        </div>
      </SectionWrapper>
    </>
  )
}
