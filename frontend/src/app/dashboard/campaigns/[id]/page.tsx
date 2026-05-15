"use client"

import React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useApiClient } from "@/hooks/useApiClient"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog"
import {
  PlayCircle, PauseCircle, Loader2, ArrowLeft,
  Mail, MessageSquareReply, Users, CheckCircle2,
  XCircle, Clock, SkipForward, MailOpen, TrendingUp, Eye
} from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import type { OutreachCampaignLead, CampaignStepStat } from "@/lib/api"

// ── Helpers ────────────────────────────────────────────────────────────────────

const pct = (n: number) => `${(n * 100).toFixed(1)}%`

const STATUS_STYLES: Record<string, string> = {
  draft:     "bg-gray-100 text-gray-700 border-gray-200",
  pending:   "bg-yellow-50 text-yellow-700 border-yellow-200",
  running:   "bg-emerald-50 text-emerald-700 border-emerald-200",
  paused:    "bg-orange-50 text-orange-700 border-orange-200",
  completed: "bg-blue-50 text-blue-700 border-blue-200",
  failed:    "bg-red-50 text-red-700 border-red-200",
}

const LEAD_STATUS_ICON: Record<string, React.ReactNode> = {
  pending:      <Clock className="size-3.5 text-yellow-500" />,
  sent:         <Mail className="size-3.5 text-blue-500" />,
  replied:      <CheckCircle2 className="size-3.5 text-emerald-500" />,
  failed:       <XCircle className="size-3.5 text-red-500" />,
  skipped:      <SkipForward className="size-3.5 text-gray-400" />,
  unsubscribed: <XCircle className="size-3.5 text-gray-400" />,
}

const REPLY_BADGE: Record<string, { label: string; cls: string }> = {
  interested:      { label: "✅ Interested",       cls: "bg-emerald-100 text-emerald-700" },
  not_interested:  { label: "❌ Not Interested",   cls: "bg-red-100 text-red-700" },
  meeting_request: { label: "📅 Meeting Request",  cls: "bg-violet-100 text-violet-700" },
  objection:       { label: "🤔 Objection",        cls: "bg-orange-100 text-orange-700" },
  unknown:         { label: "Unknown",             cls: "bg-gray-100 text-gray-500" },
}

// ── Funnel Component ──────────────────────────────────────────────────────────

function CampaignFunnel({
  total_leads, total_sent, total_opened, total_replied,
}: {
  total_leads: number
  total_sent: number
  total_opened: number
  total_replied: number
}) {
  const stages = [
    { label: "Leads",   value: total_leads,   color: "bg-gray-200",          textColor: "text-gray-700" },
    { label: "Sent",    value: total_sent,    color: "bg-blue-400",          textColor: "text-blue-700" },
    { label: "Opened",  value: total_opened,  color: "bg-violet-400",        textColor: "text-violet-700" },
    { label: "Replied", value: total_replied, color: "bg-accent",            textColor: "text-white" },
  ]
  const max = total_leads || 1

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="size-4 text-accent" />
          Campaign Funnel
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {stages.map((s, i) => {
            const width = Math.max((s.value / max) * 100, s.value > 0 ? 4 : 0)
            return (
              <div key={s.label} className="flex items-center gap-4">
                <span className="text-xs font-medium text-muted-foreground w-14 shrink-0">{s.label}</span>
                <div className="flex-1 h-8 bg-muted rounded-lg overflow-hidden relative">
                  <div
                    className={`h-full rounded-lg transition-all duration-700 flex items-center justify-end pr-3 ${s.color}`}
                    style={{ width: `${width}%` }}
                  >
                    {s.value > 0 && (
                      <span className={`text-xs font-bold ${s.textColor}`}>{s.value}</span>
                    )}
                  </div>
                  {s.value === 0 && (
                    <span className="absolute inset-0 flex items-center pl-3 text-xs text-muted-foreground">0</span>
                  )}
                </div>
                {i > 0 && (
                  <span className="text-xs text-muted-foreground w-12 text-right shrink-0">
                    {max > 0 ? pct(s.value / max) : "—"}
                  </span>
                )}
                {i === 0 && <span className="w-12 shrink-0" />}
              </div>
            )
          })}
        </div>
        <div className="mt-4 pt-3 border-t border-border/50 flex gap-6 text-xs text-muted-foreground">
          <span>→ Open rate: <strong className="text-primary">{total_sent > 0 ? pct(total_opened / total_sent) : "—"}</strong></span>
          <span>→ Reply rate: <strong className="text-primary">{total_sent > 0 ? pct(total_replied / total_sent) : "—"}</strong></span>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Step Card ─────────────────────────────────────────────────────────────────

function StepCard({ s }: { s: CampaignStepStat }) {
  const dayLabel = s.step_number === 1 ? "Day 0" : s.step_number === 2 ? "Day 2" : "Day 5"
  const replyPct = s.total_sent > 0 ? (s.reply_rate * 100) : 0
  const openPct  = s.total_sent > 0 ? (s.open_rate  * 100) : 0

  return (
    <div className="rounded-xl border border-border/60 p-4 space-y-3 bg-card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Step {s.step_number}</p>
          <p className="text-xs text-muted-foreground">{dayLabel}</p>
        </div>
        <span className="text-2xl font-bold text-primary">{replyPct.toFixed(1)}%</span>
      </div>
      {/* Open rate bar */}
      <div>
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>Open rate</span><span>{openPct.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-violet-400 transition-all duration-700" style={{ width: `${Math.min(openPct, 100)}%` }} />
        </div>
      </div>
      {/* Reply rate bar */}
      <div>
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>Reply rate</span><span>{replyPct.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-emerald-400 transition-all duration-700" style={{ width: `${Math.min(replyPct, 100)}%` }} />
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">
        {s.total_replied}/{s.total_sent} replied · {s.total_opened} opened
        {s.total_failed > 0 && <span className="text-red-500"> · {s.total_failed} failed</span>}
      </p>
    </div>
  )
}

// ── Lead Row ──────────────────────────────────────────────────────────────────

function LeadRow({ lead, onViewEmail }: { lead: any, onViewEmail: (lead: any) => void }) {
  const name = [lead.first_name, lead.last_name].filter(Boolean).join(" ") || "—"
  const stepLabel = lead.current_step === 0 ? "Not started" : `Step ${lead.current_step}`
  const badge = lead.reply_type ? REPLY_BADGE[lead.reply_type] || REPLY_BADGE.unknown : null

  return (
    <tr className="border-b border-border/50 hover:bg-muted/20 transition-colors">
      <td className="py-3 px-4">
        <div className="font-medium text-sm">{name}</div>
        <div className="text-xs text-muted-foreground">{lead.email}</div>
      </td>
      <td className="py-3 px-4 text-xs text-muted-foreground">{lead.company || "—"}</td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5 text-xs">
          {LEAD_STATUS_ICON[lead.status] ?? null}
          <span className="capitalize">{lead.status}</span>
        </div>
      </td>
      <td className="py-3 px-4 text-xs text-muted-foreground">{stepLabel}</td>
      <td className="py-3 px-4">
        {badge ? (
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        ) : "—"}
      </td>
      <td className="py-3 px-4 text-xs text-muted-foreground max-w-[200px] truncate">
        {lead.reply_summary || "—"}
      </td>
      <td className="py-3 px-4 text-right">
        {(lead.subject || lead.body) ? (
          <Button variant="ghost" size="sm" className="h-8 px-2 text-xs" onClick={() => onViewEmail(lead)}>
            <Eye className="size-3 mr-1" /> View Email
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const api = useApiClient()
  const queryClient = useQueryClient()
  
  const [selectedEmail, setSelectedEmail] = React.useState<any>(null)

  const { data: detail, isLoading } = useQuery({
    queryKey: ["outreach-campaign", id],
    queryFn: () => api.outreach.detail(id),
    staleTime: 10_000,
    refetchInterval: 20_000,
  })

  const { data: stats } = useQuery({
    queryKey: ["outreach-campaign-stats", id],
    queryFn: () => api.outreach.stats(id),
    staleTime: 10_000,
    enabled: !!id,
  })

  const runMutation = useMutation({
    mutationFn: () => api.outreach.run(id),
    onSuccess: () => {
      toast.success("Campaign started!")
      queryClient.invalidateQueries({ queryKey: ["outreach-campaign", id] })
      queryClient.invalidateQueries({ queryKey: ["outreach-campaigns"] })
    },
  })

  const pauseMutation = useMutation({
    mutationFn: () => api.outreach.pause(id),
    onSuccess: () => {
      toast.success("Campaign paused.")
      queryClient.invalidateQueries({ queryKey: ["outreach-campaign", id] })
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">Campaign not found.</p>
        <Button variant="link" asChild><Link href="/dashboard/campaigns">← Back</Link></Button>
      </div>
    )
  }

  const openRate  = detail.total_sent > 0 ? pct((detail as any).total_opened / detail.total_sent) : "—"
  const replyRate = detail.total_sent > 0 ? pct(detail.reply_rate) : "—"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/dashboard/campaigns"><ArrowLeft className="size-4" /></Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{detail.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Score filter: ≥ {detail.min_score_filter !== null ? `${((detail.min_score_filter ?? 0) * 100).toFixed(0)}%` : "—"}
              <span className="mx-2 text-border">·</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[detail.status] || STATUS_STYLES.draft}`}>
                {detail.status}
              </span>
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {(detail.status === "draft" || detail.status === "paused") && (
            <Button size="sm" variant="primary" onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              {runMutation.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <PlayCircle className="mr-2 size-4" />}
              {detail.status === "paused" ? "Resume" : "Launch Sequence"}
            </Button>
          )}
          {detail.status === "running" && (
            <Button size="sm" variant="outline" onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}>
              {pauseMutation.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <PauseCircle className="mr-2 size-4" />}
              Pause
            </Button>
          )}
        </div>
      </div>

      {/* KPI Stats row — 5 cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {[
          { label: "Total Leads",  value: detail.total_leads,   icon: <Users className="size-4 text-muted-foreground" /> },
          { label: "Emails Sent",  value: detail.total_sent,    icon: <Mail className="size-4 text-blue-500" /> },
          { label: "Opened",       value: (detail as any).total_opened ?? 0, icon: <MailOpen className="size-4 text-violet-500" /> },
          { label: "Open Rate",    value: openRate,             icon: <MailOpen className="size-4 text-violet-400" /> },
          { label: "Reply Rate",   value: replyRate,            icon: <CheckCircle2 className="size-4 text-emerald-500" /> },
        ].map(s => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3 pt-5 pb-4">
              {s.icon}
              <div>
                <p className="text-xs text-muted-foreground">{s.label}</p>
                <p className="text-2xl font-bold">{s.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Funnel */}
      <CampaignFunnel
        total_leads={detail.total_leads}
        total_sent={detail.total_sent}
        total_opened={(detail as any).total_opened ?? 0}
        total_replied={detail.total_replied}
      />

      {/* Step performance */}
      {stats && stats.step_stats.length > 0 && (
        <div>
          <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
            <MessageSquareReply className="size-4 text-accent" />
            Sequence Performance by Step
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {stats.step_stats.map(s => <StepCard key={s.step_number} s={s} />)}
          </div>
        </div>
      )}

      {/* Leads table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Leads in Sequence ({detail.leads.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/30">
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">Contact</th>
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">Company</th>
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">Status</th>
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">Step</th>
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">Reply Type</th>
                  <th className="py-2.5 px-4 text-left text-xs font-semibold text-muted-foreground">AI Summary</th>
                  <th className="py-2.5 px-4 text-right text-xs font-semibold text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {detail.leads.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-muted-foreground text-sm">
                      No leads in this campaign yet.
                    </td>
                  </tr>
                ) : (
                  detail.leads.map(lead => <LeadRow key={lead.campaign_lead_id} lead={lead} onViewEmail={setSelectedEmail} />)
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={!!selectedEmail} onOpenChange={() => setSelectedEmail(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>Generated Email Draft</DialogTitle>
            <DialogDescription>
              This is the AI-generated email for {[selectedEmail?.first_name, selectedEmail?.last_name].filter(Boolean).join(" ") || "this lead"}.
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-4 py-4 min-h-0">
            {selectedEmail && (
              <>
                <div className="space-y-1 border-b pb-4 shrink-0">
                  <p className="text-sm"><span className="font-semibold w-16 inline-block">To:</span> {selectedEmail.email}</p>
                  <p className="text-sm"><span className="font-semibold w-16 inline-block">Subject:</span> {selectedEmail.subject || "No subject"}</p>
                </div>
                <div className="bg-muted/30 p-5 rounded-xl whitespace-pre-wrap text-sm text-gray-800 leading-relaxed font-sans border border-border/50 shadow-sm">
                  {selectedEmail.body || "No email body generated."}
                </div>
              </>
            )}
          </div>

          <DialogFooter className="pt-2 border-t shrink-0">
            <Button onClick={() => setSelectedEmail(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  )
}
