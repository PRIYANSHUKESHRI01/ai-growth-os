"use client"

import { use } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowLeft, TrendingUp, Cpu, Briefcase, Zap, ShieldCheck, Target } from "lucide-react"
import { useRouter } from "next/navigation"
import { useLead, useLeadExplanation } from "@/hooks/useLeads"
import { Skeleton } from "@/components/ui/skeleton"

export default function LeadDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter()
  const { id } = use(params)
  
  const { data: lead, isLoading: leadLoading } = useLead(id)
  const { data: explanation, isLoading: explLoading } = useLeadExplanation(id)

  const isLoading = leadLoading || explLoading

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-24" />
        <div className="space-y-2">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-6 w-48" />
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <p className="text-secondary text-lg">Lead not found.</p>
        <Button onClick={() => router.push("/dashboard/leads")}>Go Back</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => router.back()} className="-ml-2">
        <ArrowLeft className="mr-2 size-4" /> Back
      </Button>

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-primary">
            {lead.first_name} {lead.last_name || ""}
          </h1>
          {explanation && (
            <Badge variant={explanation.tag.toLowerCase().includes("hot") ? "hot" : "warm"}>
              {explanation.tag}
            </Badge>
          )}
        </div>
        <p className="text-lg text-secondary">
          {lead.title} at <span className="text-primary font-medium">{lead.company}</span>
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>AI Intelligence Report</CardTitle>
            <p className="text-sm text-secondary">
               Calculated using {explanation?.intent_label || "Machine Learning"} signals and intent data.
            </p>
          </CardHeader>
          <CardContent className="space-y-8">
             <div className="mt-4 flex flex-col items-center justify-center p-6 bg-bg/50 rounded-2xl border border-border">
                <div className="text-5xl font-extrabold text-primary mb-2">
                   {Math.round((explanation?.score || lead.score?.final_score || 0) * 100)}
                </div>
                <div className="text-sm font-medium text-secondary uppercase tracking-widest">
                   Propensity Score
                </div>
             </div>

             <div className="space-y-4">
                <div className="flex justify-between items-center text-sm">
                   <span className="text-secondary">Value Alignment</span>
                   <span className="text-primary font-medium">{Math.round((explanation?.value_score || 0) * 100)}%</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                   <div 
                      className="bg-accent h-full transition-all duration-1000" 
                      style={{ width: `${(explanation?.value_score || 0) * 100}%` }}
                   />
                </div>
                
                <div className="flex justify-between items-center text-sm">
                   <span className="text-secondary">Data Confidence</span>
                   <span className="text-primary font-medium">{Math.round((explanation?.confidence_score || 0) * 100)}%</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                   <div 
                      className="bg-primary h-full transition-all duration-1000" 
                      style={{ width: `${(explanation?.confidence_score || 0) * 100}%` }}
                   />
                </div>
             </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
             <CardTitle>Decision Logic</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {explanation?.top_reasons.map((reason, i) => (
              <div key={i} className="flex gap-4">
                <div className="size-10 rounded-full bg-accent/10 flex items-center justify-center shrink-0">
                  {i === 0 ? <Target className="text-accent size-5" /> : (i === 1 ? <Briefcase className="text-accent size-5" /> : <Cpu className="text-accent size-5" />)}
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-primary">Intelligence Signal #{i+1}</h4>
                  <p className="text-xs text-secondary mt-1">{reason}</p>
                </div>
              </div>
            ))}
            
            {(!explanation || explanation.top_reasons.length === 0) && (
               <div className="flex flex-col items-center justify-center h-full text-center p-8 space-y-2">
                  <ShieldCheck className="size-12 text-border" />
                  <p className="text-sm text-secondary">Analyzing behavioral signals and metadata...</p>
               </div>
            )}
          </CardContent>
        </Card>
        
        <Card className="col-span-full">
           <CardHeader>
              <CardTitle>AI Summary & Recommendation</CardTitle>
           </CardHeader>
           <CardContent>
              <div className="p-4 bg-bg border border-border rounded-xl">
                 <p className="text-sm leading-relaxed text-secondary italic">
                    "{explanation?.summary || "Lead is currently under analysis by the Growth OS engine. Recommend monitoring for intent signals before initiating outreach."}"
                 </p>
              </div>
              
              {explanation && (
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-primary">Value Drivers</h4>
                      <ul className="space-y-1">
                         {explanation.value_factors.map((f, i) => (
                           <li key={i} className="text-sm text-secondary flex items-center gap-2">
                              <Zap className="size-3 text-accent" /> {f}
                           </li>
                         ))}
                      </ul>
                   </div>
                   <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-primary">Confidence Factors</h4>
                      <ul className="space-y-1">
                         {explanation.confidence_factors.map((f, i) => (
                           <li key={i} className="text-sm text-secondary flex items-center gap-2">
                              <ShieldCheck className="size-3 text-primary" /> {f}
                           </li>
                         ))}
                      </ul>
                   </div>
                </div>
              )}
           </CardContent>
        </Card>
      </div>
    </div>
  )
}