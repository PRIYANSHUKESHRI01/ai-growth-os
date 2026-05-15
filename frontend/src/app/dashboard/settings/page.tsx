"use client"

import { Settings, Bell, Lock, Palette, Globe, CreditCard } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

const SETTING_SECTIONS = [
  {
    icon: Bell,
    title: "Notifications",
    description: "Configure email and in-app notification preferences.",
  },
  {
    icon: Lock,
    title: "Security",
    description: "Manage password, 2FA, and active sessions.",
  },
  {
    icon: Palette,
    title: "Appearance",
    description: "Customize your dashboard theme and display options.",
  },
  {
    icon: Globe,
    title: "Integrations",
    description: "Connect CRMs, email providers, and third-party tools.",
  },
  {
    icon: CreditCard,
    title: "Billing & Credits",
    description: "Manage your plan, invoices, and discovery credits.",
  },
]

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-primary">Settings</h1>
          <p className="text-sm text-secondary mt-1">
            Manage your account preferences, integrations, and billing.
          </p>
        </div>
        <Badge variant="secondary" className="self-start sm:self-auto px-3 py-1.5 text-xs">
          Coming Soon
        </Badge>
      </div>

      {/* Setting cards grid */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {SETTING_SECTIONS.map((section) => (
          <Card
            key={section.title}
            className="opacity-70 cursor-not-allowed border-dashed hover:opacity-80 transition-opacity"
          >
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="size-9 rounded-lg bg-accent/10 flex items-center justify-center">
                  <section.icon className="size-4 text-accent" />
                </div>
                <CardTitle className="text-sm">{section.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-xs leading-relaxed">
                {section.description}
              </CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Coming soon banner */}
      <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-border bg-card text-center space-y-3">
        <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center">
          <Settings className="size-7 text-accent" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-bold text-primary">Settings coming in the next release</p>
          <p className="text-xs text-secondary max-w-xs mx-auto leading-relaxed">
            Full account settings, integrations, and billing management will be available here soon.
          </p>
        </div>
      </div>
    </div>
  )
}
