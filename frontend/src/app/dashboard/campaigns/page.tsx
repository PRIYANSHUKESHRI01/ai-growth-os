"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useApiClient } from "@/hooks/useApiClient"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog"
import {
  PlayCircle, PauseCircle, Loader2, Megaphone, Plus,
  BarChart3, Mail, MessageSquareReply, Users, ChevronRight,
  Target, Calendar, ListFilter, Trash2
} from "lucide-react"
import Link from "next/link"
import type { OutreachCampaign } from "@/lib/api"
import { useLeads } from "@/hooks/useLeads"


// ── Status badge helper ───────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700 border-gray-200",
  pending: "bg-yellow-50 text-yellow-700 border-yellow-200",
  running: "bg-emerald-50 text-emerald-700 border-emerald-200",
  paused: "bg-orange-50 text-orange-700 border-orange-200",
  completed: "bg-blue-50 text-blue-700 border-blue-200",
  failed: "bg-red-50 text-red-700 border-red-200",
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[status] || STATUS_STYLES.draft}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// ── Create Campaign Modal ──────────────────────────────────────────────────────

function CreateCampaignModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [name, setName] = useState("")

  // Targeting Mode
  const [targetingMode, setTargetingMode] = useState<"score" | "date" | "specific">("score")

  // Score Mode State
  const [minScorePct, setMinScorePct] = useState(0)

  // Date Mode State
  const [dateFilter, setDateFilter] = useState<"all" | "today" | "week">("all")

  // Specific Leads Mode State
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([])
  const { data: leadsData, isLoading: leadsLoading } = useLeads(1, 100)
  const leads = leadsData?.leads || []

  const toggleLead = (id: string) => {
    setSelectedLeadIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const createMutation = useMutation({
    mutationFn: () => {
      const payload: any = { name: name.trim() }
      if (targetingMode === "score") {
        payload.min_score_filter = minScorePct / 100
      } else if (targetingMode === "date") {
        payload.date_filter = dateFilter
        payload.min_score_filter = 0 // Include all scored leads in date range
      } else if (targetingMode === "specific") {
        payload.lead_ids = selectedLeadIds
      }
      return api.outreach.create(payload)
    },
    onSuccess: (data: any) => {
      toast.success(data.message || "Campaign created!")
      queryClient.invalidateQueries({ queryKey: ["outreach-campaigns"] })
      setName("")
      setMinScorePct(0)
      setSelectedLeadIds([])
      onClose()
    },
  })

  const scoreLabel =
    minScorePct >= 75 ? "🔥 Very selective — only top-tier leads" :
      minScorePct >= 50 ? "🌡️ Selective — warm + hot leads" :
        minScorePct >= 25 ? "📊 Moderate — most scored leads" :
          minScorePct >= 10 ? "🌐 Broad — all leads with any score" :
            "🌐 All scored leads"

  // Warn if threshold is likely too high (common mistake)
  const highThresholdWarning = minScorePct > 50

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Outreach Campaign</DialogTitle>
          <DialogDescription>
            AI selects all scored leads above your minimum score and builds a 3-step outreach sequence.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-2">
          {/* Campaign Name */}
          <div className="space-y-2">
            <Label htmlFor="campaign-name">Campaign Name</Label>
            <Input
              id="campaign-name"
              placeholder="e.g. Q2 SaaS Founders Outreach"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          {/* Targeting Mode Selector */}
          <div className="space-y-2">
            <Label>Targeting Mode</Label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setTargetingMode("score")}
                className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border transition-all ${targetingMode === "score"
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-card border-border/60 text-secondary hover:bg-muted"
                  }`}
              >
                <Target className="size-3.5" />
                By Score
              </button>
              <button
                type="button"
                onClick={() => setTargetingMode("date")}
                className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border transition-all ${targetingMode === "date"
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-card border-border/60 text-secondary hover:bg-muted"
                  }`}
              >
                <Calendar className="size-3.5" />
                By Date
              </button>
              <button
                type="button"
                onClick={() => setTargetingMode("specific")}
                className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border transition-all ${targetingMode === "specific"
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-card border-border/60 text-secondary hover:bg-muted"
                  }`}
              >
                <ListFilter className="size-3.5" />
                Specific
              </button>
            </div>
          </div>

          {/* Mode: By Score */}
          {targetingMode === "score" && (
            <div className="space-y-3 animate-in fade-in slide-in-from-top-1">
              <div className="flex items-center justify-between">
                <Label htmlFor="min-score-slider">Minimum Lead Score</Label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    min={0} max={100} step={5}
                    value={minScorePct}
                    onChange={e => {
                      const v = Math.min(100, Math.max(0, Number(e.target.value)))
                      setMinScorePct(v)
                    }}
                    className="w-14 h-7 text-center text-sm font-bold rounded-md border border-border bg-card text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
                  />
                  <span className="text-sm text-secondary font-medium">/ 100</span>
                </div>
              </div>

              {/* Range slider */}
              <div className="relative">
                <input
                  id="min-score-slider"
                  type="range"
                  min={0} max={100} step={5}
                  value={minScorePct}
                  onChange={e => setMinScorePct(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer accent-accent"
                />
                <div className="flex justify-between text-[10px] text-secondary mt-1 px-0.5">
                  <span>0</span>
                  <span>25</span>
                  <span>50</span>
                  <span>75</span>
                  <span>100</span>
                </div>
              </div>

              {/* Dynamic label */}
              <p className="text-xs text-secondary bg-card border border-border/60 rounded-lg px-3 py-2">
                {minScorePct === 0 ? "🌐 All scored leads" : `${scoreLabel} — leads with score ≥ ${minScorePct}%`}
              </p>

              {/* Warning when threshold is set very high */}
              {highThresholdWarning && (
                <p className="text-xs text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                  ⚠️ Scores above {minScorePct}% may exclude most leads. Try{" "}
                  <button
                    type="button"
                    className="underline font-semibold"
                    onClick={() => setMinScorePct(0)}
                  >
                    resetting to 0%
                  </button>{" "}
                  if the campaign shows 0 leads.
                </p>
              )}
            </div>
          )}

          {/* Mode: By Date */}
          {targetingMode === "date" && (
            <div className="space-y-3 animate-in fade-in slide-in-from-top-1">
              <Label>Filter Scored Leads By Date Added</Label>
              <div className="grid grid-cols-1 gap-2">
                {[{ id: "all", label: "All Time (All Scored Leads)" },
                { id: "week", label: "Past 7 Days" },
                { id: "today", label: "Added Today" }
                ].map(opt => (
                  <label
                    key={opt.id}
                    className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-all ${dateFilter === opt.id ? "bg-accent/5 border-accent/30" : "bg-card border-border/60 hover:bg-muted"
                      }`}
                  >
                    <input
                      type="radio"
                      name="date_filter"
                      value={opt.id}
                      checked={dateFilter === opt.id}
                      onChange={() => setDateFilter(opt.id as any)}
                      className="accent-accent size-4"
                    />
                    <span className="text-sm font-medium">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Mode: Specific Leads */}
          {targetingMode === "specific" && (
            <div className="space-y-3 animate-in fade-in slide-in-from-top-1">
              <div className="flex items-center justify-between">
                <Label>Select Specific Leads</Label>
                <span className="text-xs text-secondary">{selectedLeadIds.length} selected</span>
              </div>
              <div className="h-48 overflow-y-auto border border-border/60 rounded-lg bg-card p-1 space-y-1">
                {leadsLoading ? (
                  <div className="p-4 text-center text-sm text-secondary">Loading leads...</div>
                ) : leads.length === 0 ? (
                  <div className="p-4 text-center text-sm text-secondary">No leads found.</div>
                ) : (
                  leads.map(lead => (
                    <label
                      key={lead.id}
                      className={`flex items-center gap-3 p-2 rounded-md cursor-pointer transition-all ${selectedLeadIds.includes(lead.id) ? "bg-accent/5" : "hover:bg-muted"
                        }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.includes(lead.id)}
                        onChange={() => toggleLead(lead.id)}
                        className="accent-accent rounded size-3.5"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {lead.first_name} {lead.last_name || ""}
                        </p>
                        <p className="text-[10px] text-secondary truncate">{lead.email}</p>
                      </div>
                      <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                        {lead.score?.final_score !== undefined ? `${(lead.score.final_score * 100).toFixed(0)}%` : 'Unscored'}
                      </Badge>
                    </label>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Info box */}
          <div className="rounded-lg bg-muted/40 border border-border/60 p-3 text-xs text-muted-foreground space-y-1">
            <p>📨 Step 1 sent immediately on launch</p>
            <p>📆 Follow-up (Step 2) auto-sent on Day 2</p>
            <p>📆 Break-up (Step 3) auto-sent on Day 5</p>
            <p>🛡️ Safety: pauses if bounce rate &gt; 20%</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <><Loader2 className="mr-2 size-4 animate-spin" />Creating…</>
            ) : (
              <><Plus className="mr-2 size-4" />Create Campaign</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Campaign Card ─────────────────────────────────────────────────────────────

function CampaignCard({ campaign }: { campaign: OutreachCampaign }) {
  const api = useApiClient()
  const queryClient = useQueryClient()

  const runMutation = useMutation({
    mutationFn: () => api.outreach.run(campaign.id),
    onSuccess: () => {
      toast.success(`Campaign "${campaign.name}" started!`)
      queryClient.invalidateQueries({ queryKey: ["outreach-campaigns"] })
    },
  })

  const pauseMutation = useMutation({
    mutationFn: () => api.outreach.pause(campaign.id),
    onSuccess: () => {
      toast.success(`Campaign "${campaign.name}" paused.`)
      queryClient.invalidateQueries({ queryKey: ["outreach-campaigns"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.outreach.delete(campaign.id),
    onSuccess: () => {
      toast.success(`Campaign "${campaign.name}" deleted.`)
      queryClient.invalidateQueries({ queryKey: ["outreach-campaigns"] })
    },
  })

  const replyRate = campaign.total_sent > 0
    ? `${(campaign.reply_rate * 100).toFixed(1)}%`
    : "—"

  return (
    <Card className="group hover:border-accent/60 transition-all duration-200 hover:shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-tight line-clamp-2">{campaign.name}</CardTitle>
          <StatusBadge status={campaign.status} />
        </div>
        <CardDescription className="text-xs mt-1">
          Score filter: ≥ {campaign.min_score_filter !== null ? `${(campaign.min_score_filter * 100).toFixed(0)}%` : "—"}
          <span className="mx-1.5 text-border">·</span>
          {new Date(campaign.created_at).toLocaleDateString()}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-2 text-center rounded-lg bg-muted/30 p-2">
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Leads</p>
            <div className="flex items-center justify-center gap-1 mt-0.5">
              <Users className="size-3 text-muted-foreground" />
              <p className="text-sm font-bold">{campaign.total_leads}</p>
            </div>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Sent</p>
            <div className="flex items-center justify-center gap-1 mt-0.5">
              <Mail className="size-3 text-blue-500" />
              <p className="text-sm font-bold text-blue-600">{campaign.total_sent}</p>
            </div>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Replies</p>
            <div className="flex items-center justify-center gap-1 mt-0.5">
              <MessageSquareReply className="size-3 text-emerald-500" />
              <p className="text-sm font-bold text-emerald-600">{replyRate}</p>
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          {(campaign.status === "draft" || campaign.status === "paused") && (
            <Button
              size="sm"
              className="flex-1 text-xs"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? (
                <Loader2 className="mr-1.5 size-3 animate-spin" />
              ) : (
                <PlayCircle className="mr-1.5 size-3" />
              )}
              {campaign.status === "paused" ? "Resume" : "Launch"}
            </Button>
          )}
          {campaign.status === "running" && (
            <Button
              size="sm"
              variant="outline"
              className="flex-1 text-xs"
              onClick={() => pauseMutation.mutate()}
              disabled={pauseMutation.isPending}
            >
              {pauseMutation.isPending ? (
                <Loader2 className="mr-1.5 size-3 animate-spin" />
              ) : (
                <PauseCircle className="mr-1.5 size-3" />
              )}
              Pause
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="text-xs px-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => {
              if (confirm("Are you sure you want to delete this campaign? This action cannot be undone.")) {
                deleteMutation.mutate()
              }
            }}
            disabled={deleteMutation.isPending}
            title="Delete Campaign"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Trash2 className="size-3" />
            )}
          </Button>

          <Button size="sm" variant="ghost" className="text-xs px-2" asChild>
            <Link href={`/dashboard/campaigns/${campaign.id}`}>
              <ChevronRight className="size-3" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CampaignsPage() {
  const api = useApiClient()
  const [showCreate, setShowCreate] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ["outreach-campaigns"],
    queryFn: () => api.outreach.list(1, 50),
    staleTime: 30_000,
    refetchInterval: 15_000, // poll every 15s while running
  })

  const campaigns = data?.campaigns || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Outreach Engine</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Step 3 of your pipeline — launch AI-powered outreach sequences. {data?.total ? `${data.total} total` : ""}
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="self-start sm:self-auto">
          <Plus className="mr-2 size-4" /> New Campaign
        </Button>
      </div>

      {/* Stats row */}
      {campaigns.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Total Campaigns", value: data?.total ?? 0, icon: <BarChart3 className="size-4 text-muted-foreground" /> },
            { label: "Running", value: campaigns.filter(c => c.status === "running").length, icon: <PlayCircle className="size-4 text-emerald-500" /> },
            { label: "Emails Sent", value: campaigns.reduce((s, c) => s + c.total_sent, 0), icon: <Mail className="size-4 text-blue-500" /> },
            { label: "Replies", value: campaigns.reduce((s, c) => s + c.total_replied, 0), icon: <MessageSquareReply className="size-4 text-violet-500" /> },
          ].map(stat => (
            <Card key={stat.label} className="py-3">
              <CardContent className="flex items-center gap-3 px-4 py-0">
                {stat.icon}
                <div>
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                  <p className="text-xl font-bold">{stat.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Campaign grid */}
      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-52 w-full rounded-xl" />)}
        </div>
      ) : campaigns.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="h-64 flex flex-col items-center justify-center text-center space-y-4">
            <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center">
              <Megaphone className="size-6 text-accent" />
            </div>
            <div>
              <p className="text-lg font-bold">No campaigns yet</p>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1">
                Score your leads first, then create a campaign to launch an AI-powered 3-step outreach sequence.
              </p>
            </div>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 size-4" /> Create First Campaign
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {campaigns.map(c => <CampaignCard key={c.id} campaign={c} />)}
        </div>
      )}

      <CreateCampaignModal open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  )
}