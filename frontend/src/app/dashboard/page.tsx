"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useDashboardStats } from "@/hooks/useStats"
import { useTopLeads, useUploadLeads } from "@/hooks/useLeads"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useRouter } from "next/navigation"
import {
  Search, UploadCloud, Loader2, Users, BrainCircuit, Flame,
  Megaphone, Zap, ChevronRight, ArrowRight, CheckCircle2,
  Circle, Clock, AlertTriangle
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useRef } from "react"
import { toast } from "sonner"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { useApiClient } from "@/hooks/useApiClient"

// ─────────────────────────────────────────────────────────────────────────────
// PIPELINE PROGRESS BAR — with checkmarks, status labels, live counts
// ─────────────────────────────────────────────────────────────────────────────
function PipelineProgressBar({ totalLeads, hotLeads, campaignsCount }: {
  totalLeads: number
  hotLeads: number
  campaignsCount: number
}) {
  const discoverDone = totalLeads > 0
  const scoreDone = hotLeads > 0
  const outreachDone = campaignsCount > 0

  // Determine status text for each step
  function getStatus(done: boolean, prev: boolean): "completed" | "in-progress" | "not-started" {
    if (done) return "completed"
    if (prev) return "in-progress"
    return "not-started"
  }

  const discoverStatus = getStatus(discoverDone, true)
  const scoreStatus = getStatus(scoreDone, discoverDone)
  const outreachStatus = getStatus(outreachDone, scoreDone)

  const STATUS_LABEL: Record<string, string> = {
    "completed": "Completed",
    "in-progress": "In Progress",
    "not-started": "Not Started",
  }

  const steps = [
    {
      id: "discover",
      label: "Lead Discovery",
      automation: "Prospecting",
      href: "/dashboard/discovery",
      status: discoverStatus,
      count: discoverDone ? `${totalLeads} leads` : "0 leads",
    },
    {
      id: "score",
      label: "Lead Scoring",
      automation: "Lead Discovery",
      href: "/dashboard/leads",
      status: scoreStatus,
      count: hotLeads > 0 ? `${hotLeads} hot leads` : totalLeads > 0 ? "Awaiting scoring" : "—",
    },
    {
      id: "outreach",
      label: "Outreach Engine",
      automation: "Outreach Engine",
      href: "/dashboard/campaigns",
      status: outreachStatus,
      count: outreachDone ? `${campaignsCount} active` : "—",
    },
  ]

  return (
    <div className="w-full rounded-2xl border border-border bg-card p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 mb-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-secondary">Pipeline Status</p>
        <p className="text-[11px] text-secondary">Follow the steps to activate your growth engine.</p>
      </div>
      {/* Mobile: vertical stack. sm+: horizontal row */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-0">
        {steps.map((step, i) => {
          const isCompleted = step.status === "completed"
          const isInProgress = step.status === "in-progress"
          const isNotStarted = step.status === "not-started"

          return (
            <div key={step.id} className="flex sm:flex-col sm:items-start sm:flex-1">
              {/* Mobile: horizontal row. sm+: stacked column */}
              <Link href={step.href} className="flex-1 group flex sm:flex-col items-center sm:text-center gap-3 sm:gap-2 py-2 sm:py-0">

                {/* Circle / checkmark */}
                <div className={`
                  size-9 sm:size-10 rounded-full flex items-center justify-center border-2 transition-all duration-200 group-hover:scale-110 shrink-0
                  ${isCompleted ? "bg-emerald-500/10 border-emerald-500 text-emerald-500 shadow-[0_0_16px_-4px_rgba(16,185,129,0.5)]" : ""}
                  ${isInProgress ? "bg-accent/10 border-accent text-accent shadow-[0_0_16px_-4px_hsl(var(--accent)/0.4)] animate-pulse" : ""}
                  ${isNotStarted ? "bg-bg border-border text-secondary/40" : ""}
                `}>
                  {isCompleted && <CheckCircle2 className="size-4 sm:size-5" />}
                  {isInProgress && <Clock className="size-4 sm:size-5" />}
                  {isNotStarted && <Circle className="size-3.5 sm:size-4" />}
                </div>

                {/* Text */}
                <div className="space-y-0.5 text-left sm:text-center">
                  <p className={`text-xs font-bold leading-tight transition-colors ${isCompleted ? "text-emerald-500" : isInProgress ? "text-primary" : "text-secondary/50"}`}>
                    {step.label}
                  </p>
                  <p className={`text-[10px] font-medium ${isCompleted ? "text-emerald-400" : isInProgress ? "text-accent" : "text-secondary/30"}`}>
                    {STATUS_LABEL[step.status]}
                  </p>
                  <p className={`text-[10px] font-mono ${isCompleted ? "text-secondary" : isInProgress ? "text-secondary" : "text-secondary/30"}`}>
                    {step.count}
                  </p>
                </div>
              </Link>

              {i < steps.length - 1 && (
                <div className="pl-2 sm:pt-4 sm:px-2 shrink-0 flex items-center sm:self-start">
                  <ArrowRight className={`size-4 rotate-90 sm:rotate-0 transition-colors ${steps[i + 1].status !== "not-started" ? "text-accent" : "text-border"}`} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// SMART PRIMARY CTA
// ─────────────────────────────────────────────────────────────────────────────
function SmartCTA({ totalLeads, hotLeads }: { totalLeads: number; hotLeads: number }) {
  const router = useRouter()

  let label = "Run Discovery"
  let href = "/dashboard/discovery"
  let icon = <Zap className="size-4" />
  let hint = "No leads yet — start your pipeline by discovering new prospects."

  if (totalLeads > 0 && hotLeads === 0) {
    label = "Review Leads"
    href = "/dashboard/leads"
    icon = <BrainCircuit className="size-4" />
    hint = "Leads found — check your AI scoring results and identify high-intent prospects."
  } else if (hotLeads > 0) {
    label = "Launch Campaign"
    href = "/dashboard/campaigns"
    icon = <Megaphone className="size-4" />
    hint = `${hotLeads} hot lead${hotLeads !== 1 ? "s" : ""} ready for outreach — launch an AI-powered sequence now.`
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 px-4 sm:px-5 py-4 rounded-xl bg-accent/5 border border-accent/20 transition-all duration-200 hover:bg-accent/8 hover:border-accent/30">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <div className="size-9 rounded-full bg-accent/15 flex items-center justify-center text-accent shrink-0">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-primary">Next recommended action</p>
          <p className="text-xs text-secondary mt-0.5 leading-relaxed">{hint}</p>
        </div>
      </div>
      <Button
        variant="primary"
        size="sm"
        className="shrink-0 gap-2 transition-all duration-200 hover:scale-[1.03] w-full sm:w-auto"
        onClick={() => router.push(href)}
      >
        {label}
        <ChevronRight className="size-3.5" />
      </Button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// STAT CARD — clickable with hover lift
// ─────────────────────────────────────────────────────────────────────────────
function StatCard({
  title, value, loading, detail, icon: Icon, href
}: {
  title: string
  value?: string | number
  loading: boolean
  detail?: string
  icon: React.ElementType
  href?: string
}) {
  const router = useRouter()
  return (
    <Card
      className={`transition-all duration-200 ${href ? "cursor-pointer hover:shadow-lg hover:scale-[1.02] hover:-translate-y-0.5 active:scale-[0.99]" : ""}`}
      onClick={href ? () => router.push(href) : undefined}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-secondary">{title}</CardTitle>
        <Icon className="size-4 text-accent" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <>
            <div className="text-2xl font-bold text-primary">
              {value !== undefined && value !== null ? value : "—"}
            </div>
            {detail && <p className="text-xs text-secondary mt-1">{detail}</p>}
            {href && (
              <p className="text-[10px] text-accent/60 mt-1.5 font-medium uppercase tracking-wide">
                Click to view →
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION HEADER — numbered badge + link
// ─────────────────────────────────────────────────────────────────────────────
function SectionHeader({
  step, title, subtitle, href, linkLabel
}: {
  step: number; title: string; subtitle: string; href: string; linkLabel: string
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="size-7 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center text-accent text-xs font-bold">
          {step}
        </div>
        <div>
          <h2 className="text-base font-bold text-primary">{title}</h2>
          <p className="text-xs text-secondary">{subtitle}</p>
        </div>
      </div>
      <Link
        href={href}
        className="flex items-center gap-1 text-xs font-medium text-accent hover:text-accent/80 transition-colors"
      >
        {linkLabel} <ChevronRight className="size-3" />
      </Link>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// CONFIDENCE BADGE helper
// ─────────────────────────────────────────────────────────────────────────────
function ConfidenceBadge({ value }: { value?: number }) {
  if (value === undefined || value === null) return <span className="text-secondary text-xs">—</span>
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? "text-emerald-500" : pct >= 40 ? "text-amber-500" : "text-red-400"
  return <span className={`text-xs font-bold ${color}`}>{pct}%</span>
}

// ─────────────────────────────────────────────────────────────────────────────
// SOURCE BADGE helper  (source field: "discovery" | "upload" | "api" | null)
// ─────────────────────────────────────────────────────────────────────────────
function SourceBadge({ source }: { source?: string | null }) {
  if (!source) return <span className="text-secondary text-xs">—</span>
  const isDiscovery = source.toLowerCase().includes("discovery") || source.toLowerCase().includes("mock") || source.toLowerCase().includes("apollo")
  return (
    <span className={`
      inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border
      ${isDiscovery
        ? "bg-accent/10 text-accent border-accent/20"
        : "bg-secondary/10 text-secondary border-border"
      }
    `}>
      {isDiscovery ? "Discovery" : source === "api" ? "Upload" : source}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
export default function DashboardOverview() {
  const router = useRouter()
  const api = useApiClient()
  const { data: stats, isLoading: statsLoading } = useDashboardStats()
  const { data: topLeads, isLoading: leadsLoading } = useTopLeads(5)
  const { mutate: uploadLeads, isPending: isUploading } = useUploadLeads()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: campaignsData } = useQuery({
    queryKey: ["outreach-campaigns"],
    queryFn: () => api.outreach.list(1, 50),
    staleTime: 30_000,
  })

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""
    uploadLeads(file, {
      onSuccess: (res) => { toast.success(`Successfully uploaded ${res.created} leads!`) }
    })
  }

  const totalLeads = stats?.total_leads ?? 0
  const hotLeads = stats?.hot_leads_count ?? 0
  const campaignsCount = stats?.campaigns_count ?? 0

  return (
    <div className="space-y-8 sm:space-y-10">

      {/* ── HERO SECTION ── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-4xl font-bold tracking-tight text-primary">Your Growth Engine</h1>
          <p className="text-sm text-secondary mt-2 max-w-lg leading-relaxed">
            Turn cold leads into revenue with AI-powered discovery, scoring, and outreach.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".csv,.json"
            className="hidden"
          />
          <Button
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
            className="gap-2 transition-all duration-200 hover:scale-[1.02]"
            variant="secondary"
            size="sm"
          >
            {isUploading ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
            {isUploading ? "Uploading..." : "Upload Leads"}
          </Button>
        </div>
      </div>

      {/* ── PIPELINE PROGRESS BAR ── */}
      {statsLoading ? (
        <Skeleton className="h-36 w-full rounded-2xl" />
      ) : (
        <PipelineProgressBar
          totalLeads={totalLeads}
          hotLeads={hotLeads}
          campaignsCount={campaignsCount}
        />
      )}

      {/* ── SMART PRIMARY CTA ── */}
      {!statsLoading && (
        <SmartCTA totalLeads={totalLeads} hotLeads={hotLeads} />
      )}

      {/* ── STAT CARDS ── */}
      <div className="grid gap-4 sm:gap-6 grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Leads"
          value={stats?.total_leads}
          loading={statsLoading}
          icon={Users}
          href="/dashboard/leads"
        />
        <StatCard
          title="Avg. Intelligence"
          value={stats ? `${(stats.avg_score * 100).toFixed(1)}%` : undefined}
          loading={statsLoading}
          icon={BrainCircuit}
        />
        <StatCard
          title="Hot Leads"
          value={stats?.hot_leads_count}
          loading={statsLoading}
          detail="Score ≥ 80"
          icon={Flame}
          href="/dashboard/leads?tag=HOT"
        />
        <StatCard
          title="Active Campaigns"
          value={stats?.campaigns_count}
          loading={statsLoading}
          icon={Megaphone}
          href="/dashboard/campaigns"
        />
      </div>

      {/* ══════════════════════════════════════════════════════ */}
      {/* SECTION 1 — DISCOVER LEADS                           */}
      {/* ══════════════════════════════════════════════════════ */}
      <div className="space-y-4">
        <SectionHeader
          step={1}
          title="Discover Leads"
          subtitle="Lead Discovery — find and enrich high-intent prospects"
          href="/dashboard/discovery"
          linkLabel="Open Discovery"
        />
        {totalLeads === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-border bg-card text-center space-y-4 transition-colors duration-200 hover:border-accent/30">
            <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center text-accent">
              <Zap className="size-7" />
            </div>
            <div className="space-y-1.5">
              <p className="text-sm font-bold text-primary">No leads yet. Start your pipeline.</p>
              <p className="text-xs text-secondary max-w-[280px] mx-auto leading-relaxed">
                Discover new high-intent prospects by defining your ideal customer profile and running the AI discovery engine.
              </p>
            </div>
            <Button variant="primary" size="sm" onClick={() => router.push("/dashboard/discovery")} className="gap-2 transition-all duration-200 hover:scale-[1.03]">
              <Zap className="size-3.5" /> Run Discovery
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: "Total Discovered", value: stats?.total_leads ?? 0 },
              { label: "High Intent (Hot)", value: stats?.hot_leads_count ?? 0 },
              { label: "Avg AI Score", value: stats ? `${(stats.avg_score * 100).toFixed(0)}%` : "—" },
            ].map(stat => (
              <div
                key={stat.label}
                className="rounded-xl border border-border bg-card p-5 text-center transition-all duration-200 hover:shadow-md hover:scale-[1.02] cursor-pointer"
                onClick={() => router.push("/dashboard/discovery")}
              >
                <p className="text-[10px] font-bold uppercase text-secondary tracking-wider">{stat.label}</p>
                <p className="text-2xl font-bold text-primary mt-1.5">{stat.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════ */}
      {/* SECTION 2 — SCORE & ANALYZE                          */}
      {/* ══════════════════════════════════════════════════════ */}
      <div className="space-y-4">
        <SectionHeader
          step={2}
          title="Score & Analyze"
          subtitle="Lead Discovery — AI-ranked leads ready for action"
          href="/dashboard/leads"
          linkLabel="View All Leads"
        />

        {/* Hot leads insight banner */}
        {!leadsLoading && totalLeads > 0 && hotLeads === 0 && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
            <AlertTriangle className="size-4 text-amber-500 shrink-0" />
            <p className="text-xs text-amber-600 dark:text-amber-400 leading-relaxed">
              No high-intent leads yet. Refine your ICP or run more discovery to improve lead quality.
            </p>
          </div>
        )}

        <Card className="col-span-full">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Recent High-Intent Leads</CardTitle>
              <Badge variant="hot">Real-time Feed</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0 border-t border-border">
            {leadsLoading ? (
              <div className="p-8 space-y-4">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            ) : (
              <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-bg/50">
                  <TableRow className="hover:bg-transparent border-border">
                    <TableHead className="pl-6">Lead</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead className="text-center">Confidence</TableHead>
                    <TableHead className="text-center">Source</TableHead>
                    <TableHead className="pr-6 text-right">Intent</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {topLeads?.leads.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-44">
                        <div className="flex flex-col items-center justify-center text-center space-y-3">
                          <div className="size-10 rounded-full bg-accent/10 flex items-center justify-center text-accent">
                            <Search className="size-5" />
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm font-bold text-primary">No scored leads available yet</p>
                            <p className="text-[11px] text-secondary max-w-[200px]">
                              Discover prospects first, then AI will score them automatically.
                            </p>
                          </div>
                          <Button variant="primary" size="sm" onClick={() => router.push("/dashboard/discovery")}>
                            Go to Discovery
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    topLeads?.leads.map((lead: any) => (
                      <TableRow
                        key={lead.id}
                        className="cursor-pointer hover:bg-bg/60 transition-all duration-150 border-border group"
                        onClick={() => router.push(`/dashboard/leads/${lead.id}`)}
                      >
                        <TableCell className="pl-6 font-medium text-primary">
                          <div>
                            <div className="group-hover:text-accent transition-colors duration-150">
                              {lead.first_name} {lead.last_name}
                            </div>
                            <div className="text-xs font-normal text-secondary">{lead.email}</div>
                          </div>
                        </TableCell>
                        <TableCell className="text-secondary">{lead.company || "—"}</TableCell>
                        <TableCell>
                          <span className="font-bold text-primary text-sm">
                            {Math.round((lead.score?.final_score || 0) * 100)}
                          </span>
                          <span className="text-secondary text-xs">/100</span>
                        </TableCell>
                        <TableCell className="text-center">
                          <ConfidenceBadge value={lead.score?.confidence_score} />
                        </TableCell>
                        <TableCell className="text-center">
                          <SourceBadge source={lead.source} />
                        </TableCell>
                        <TableCell className="pr-6 text-right">
                          <Badge variant={lead.score?.tag?.toLowerCase().includes("hot") ? "hot" : lead.score?.tag?.toLowerCase().includes("warm") ? "warm" : "cold"}>
                            {lead.score?.tag || "UNSCORED"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════ */}
      {/* SECTION 3 — RUN CAMPAIGNS                            */}
      {/* ══════════════════════════════════════════════════════ */}
      <div className="space-y-4 pb-8">
        <SectionHeader
          step={3}
          title="Run Campaigns"
          subtitle="Outreach Engine — launch AI-powered outreach sequences"
          href="/dashboard/campaigns"
          linkLabel="Manage Campaigns"
        />
        {campaignsCount === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-dashed border-border bg-card text-center space-y-4 transition-colors duration-200 hover:border-accent/30">
            <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center text-accent">
              <Megaphone className="size-7" />
            </div>
            <div className="space-y-1.5">
              <p className="text-sm font-bold text-primary">Launch your first campaign</p>
              <p className="text-xs text-secondary max-w-[280px] mx-auto leading-relaxed">
                Start converting your highest-scored leads into meetings with an AI-powered 3-step outreach sequence.
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => router.push("/dashboard/campaigns")}
              className="gap-2 transition-all duration-200 hover:scale-[1.03]"
            >
              <Megaphone className="size-3.5" /> Create First Campaign
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Total Campaigns", value: campaignsData?.total ?? 0 },
              { label: "Running", value: campaignsData?.campaigns?.filter((c: any) => c.status === "running").length ?? 0 },
              { label: "Emails Sent", value: campaignsData?.campaigns?.reduce((s: number, c: any) => s + (c.total_sent ?? 0), 0) ?? 0 },
              { label: "Replies", value: campaignsData?.campaigns?.reduce((s: number, c: any) => s + (c.total_replied ?? 0), 0) ?? 0 },
            ].map(stat => (
              <div
                key={stat.label}
                className="rounded-xl border border-border bg-card p-5 text-center cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-[1.02] hover:-translate-y-0.5 active:scale-[0.99]"
                onClick={() => router.push("/dashboard/campaigns")}
              >
                <p className="text-[10px] font-bold uppercase text-secondary tracking-wider">{stat.label}</p>
                <p className="text-2xl font-bold text-primary mt-1.5">{stat.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}