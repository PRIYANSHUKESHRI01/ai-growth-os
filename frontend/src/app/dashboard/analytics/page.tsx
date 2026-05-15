"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart3, TrendingUp, PieChart, Target } from "lucide-react"

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-primary">Intelligence Analytics</h1>
        <p className="text-sm text-secondary mt-1">Deep dive into conversion cohorts and scoring distributions.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          { title: "Conversion Rate", value: "24.8%", icon: TrendingUp },
          { title: "Pipeline Velocity", value: "12 Days", icon: BarChart3 },
          { title: "High-Intent Hotness", value: "82%", icon: Target },
          { title: "TAM Coverage", value: "12,402", icon: PieChart }
        ].map((stat, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-secondary">{stat.title}</CardTitle>
              <stat.icon className="size-4 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-primary">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="col-span-full">
         <CardHeader>
            <CardTitle>Conversion Distribution</CardTitle>
         </CardHeader>
         <CardContent className="h-[400px] flex items-center justify-center text-secondary bg-bg/50 border border-dashed border-border rounded-xl">
            Intelligence distribution chart coming in the next release.
         </CardContent>
      </Card>
    </div>
  )
}
