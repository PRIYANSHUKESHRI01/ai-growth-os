"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { GitMerge, Zap, Settings } from "lucide-react"

export default function WorkflowsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-primary">Growth Workflows</h1>
        <p className="text-sm text-secondary mt-1">Automate lead handoffs and outbound triggers.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
               <CardTitle>Lead Scoring Sequence</CardTitle>
               <Zap className="size-4 text-accent" />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
             <p className="text-sm text-secondary">Automatically trigger scoring engine when new leads are discovered or uploaded.</p>
             <div className="mt-4 p-3 bg-bg border border-border rounded-lg text-xs font-mono text-primary">
                IF new_lead THEN compute_score(lead) -&gt; notify_sales
             </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
               <CardTitle>Outreach Automation</CardTitle>
               <GitMerge className="size-4 text-accent" />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
             <p className="text-sm text-secondary">Trigger personalized email sequences for leads with score &gt; 80.</p>
             <div className="mt-4 p-3 bg-bg border border-border rounded-lg text-xs font-mono text-primary">
                IF score &gt; 0.8 THEN run_campaign(&quot;Hot Enterprise&quot;)
             </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
