"use client"

import { HelpCircle, BookOpen, Lightbulb, Code2, BarChart3, Zap } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

const HELP_TOPICS = [
  {
    icon: Zap,
    title: "Getting Started",
    description: "Learn how to set up your first discovery pipeline and find your first leads.",
  },
  {
    icon: BarChart3,
    title: "Lead Scoring",
    description: "Understand how AI scoring works and how to interpret score signals.",
  },
  {
    icon: Lightbulb,
    title: "Campaign Best Practices",
    description: "Tips for writing effective outreach sequences with high reply rates.",
  },
  {
    icon: BookOpen,
    title: "ICP Configuration",
    description: "How to define your ideal customer profile for maximum discovery precision.",
  },
  {
    icon: Code2,
    title: "API Reference",
    description: "Full REST API documentation for developers integrating AI Growth OS.",
  },
  {
    icon: HelpCircle,
    title: "FAQs",
    description: "Answers to common questions about credits, data, and privacy.",
  },
]

export default function HelpPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-primary">Help Center</h1>
          <p className="text-sm text-secondary mt-1">
            Guides, tutorials, and answers to get the most out of AI Growth OS.
          </p>
        </div>
        <Badge variant="secondary" className="self-start sm:self-auto px-3 py-1.5 text-xs">
          Coming Soon
        </Badge>
      </div>

      {/* Help topic cards */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {HELP_TOPICS.map((topic) => (
          <Card
            key={topic.title}
            className="opacity-70 border-dashed cursor-not-allowed hover:opacity-80 transition-opacity"
          >
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="size-9 rounded-lg bg-accent/10 flex items-center justify-center">
                  <topic.icon className="size-4 text-accent" />
                </div>
                <CardTitle className="text-sm">{topic.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-xs leading-relaxed">
                {topic.description}
              </CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Coming soon banner */}
      <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-border bg-card text-center space-y-3">
        <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center">
          <HelpCircle className="size-7 text-accent" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-bold text-primary">Help center coming soon</p>
          <p className="text-xs text-secondary max-w-xs mx-auto leading-relaxed">
            Full documentation, video tutorials, and an FAQ knowledge base are in the works.
          </p>
        </div>
      </div>
    </div>
  )
}
