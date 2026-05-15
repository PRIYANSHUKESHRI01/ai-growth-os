"use client"

import { LifeBuoy, MessageCircle, BookOpen, Video, Mail } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const SUPPORT_OPTIONS = [
  {
    icon: MessageCircle,
    title: "Live Chat",
    description: "Chat with our support team in real-time during business hours.",
    cta: "Start Chat",
    available: false,
  },
  {
    icon: Mail,
    title: "Email Support",
    description: "Send us a detailed message and we'll get back to you within 24 hours.",
    cta: "Send Email",
    available: false,
  },
  {
    icon: BookOpen,
    title: "Documentation",
    description: "Browse our full documentation, API references, and guides.",
    cta: "Read Docs",
    available: false,
  },
  {
    icon: Video,
    title: "Video Tutorials",
    description: "Watch step-by-step walkthroughs for every feature.",
    cta: "Watch Now",
    available: false,
  },
]

export default function SupportPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-primary">Support</h1>
          <p className="text-sm text-secondary mt-1">
            Get help from our team or browse self-service resources.
          </p>
        </div>
        <Badge variant="secondary" className="self-start sm:self-auto px-3 py-1.5 text-xs">
          Coming Soon
        </Badge>
      </div>

      {/* Support option cards */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2">
        {SUPPORT_OPTIONS.map((option) => (
          <Card
            key={option.title}
            className="opacity-70 border-dashed"
          >
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="size-9 rounded-lg bg-accent/10 flex items-center justify-center">
                  <option.icon className="size-4 text-accent" />
                </div>
                <CardTitle className="text-sm">{option.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <CardDescription className="text-xs leading-relaxed">
                {option.description}
              </CardDescription>
              <Button variant="secondary" size="sm" className="text-xs" disabled>
                {option.cta}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Coming soon banner */}
      <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-border bg-card text-center space-y-3">
        <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center">
          <LifeBuoy className="size-7 text-accent" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-bold text-primary">Support portal coming soon</p>
          <p className="text-xs text-secondary max-w-xs mx-auto leading-relaxed">
            In the meantime, reach out directly at{" "}
            <span className="text-accent font-medium">support@aigrowths.com</span>
          </p>
        </div>
      </div>
    </div>
  )
}
