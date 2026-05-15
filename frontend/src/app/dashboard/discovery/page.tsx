"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Rocket, BarChart2, Filter, AlertCircle, Loader2, PlayCircle,
  History, Download, Brain, CheckCircle2, RefreshCw, Layers, ExternalLink
} from "lucide-react"
import {
  useDiscoveryJobs,
  useCreateDiscoveryJob,
  useRunDiscoveryJobSync,
  useDownloadJobCsv,
  useSendJobToScoring,
  useDiscoveryCredits,
  useEnrichedLeads,
} from "@/hooks/useDiscovery"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"

// ── Confidence badge helper ────────────────────────────────────────────────────
function ConfBadge({ value }: { value?: number }) {
  if (value == null) return <span className="text-secondary text-xs">—</span>
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? "text-green-400" : pct >= 50 ? "text-yellow-400" : "text-red-400"
  return <span className={`font-bold text-xs ${color}`}>{pct}%</span>
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-green-500/15 text-green-400 border-green-500/30",
    running:   "bg-accent/15 text-accent border-accent/30 animate-pulse",
    pending:   "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    failed:    "bg-red-500/15 text-red-400 border-red-500/30",
  }
  const cls = map[status] ?? "bg-border/50 text-secondary"
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${cls}`}>
      {status}
    </span>
  )
}

export default function DiscoveryPage() {
  const router = useRouter()

  const [filters, setFilters] = useState({
    industry: "SaaS",
    title_keywords: "VP of Sales, Director of Engineering",
    company_size: "51-200",
    location: "United States",
    max_results: 20,
  })

  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [liveLeads, setLiveLeads] = useState<any[]>([])
  const [enrichedPage, setEnrichedPage] = useState(1)

  const { data: jobsList, isLoading: jobsLoading, refetch: refetchJobs } = useDiscoveryJobs()
  const { data: credits, refetch: refetchCredits } = useDiscoveryCredits()
  const { data: enrichedData, isLoading: enrichedLoading, refetch: refetchEnriched } = useEnrichedLeads(enrichedPage)
  const createJobMutation   = useCreateDiscoveryJob()
  const runSyncMutation     = useRunDiscoveryJobSync()
  const downloadCsvMutation = useDownloadJobCsv()
  // Navigate to leads page after scoring — the discovery endpoint already scored the right leads
  const sendScoringMutation = useSendJobToScoring(() => router.push("/dashboard/leads"))

  const isRunning = createJobMutation.isPending || runSyncMutation.isPending

  const handleStartDiscovery = async () => {
    try {
      const keywords = filters.title_keywords.split(",").map((k) => k.trim())
      const job = await createJobMutation.mutateAsync({
        ...filters,
        title_keywords: keywords,
        source_adapter: "mock",
      })

      toast.info("Discovery job created — running pipeline...")
      setActiveJobId(job.id)
      setLiveLeads([])

      const result = await runSyncMutation.mutateAsync(job.id)
      setLiveLeads(result.leads ?? [])
      refetchCredits()
      // Refresh the enriched leads panel
      refetchEnriched()
    } catch (_err) {
      // Error toast handled by mutation hooks
    }
  }

  const handleDownloadCsv = (jobId: string) => {
    downloadCsvMutation.mutate(jobId)
  }

  const handleSendToScoring = (jobId: string) => {
    sendScoringMutation.mutate(jobId)
  }

  const completedJobs = jobsList?.jobs.filter((j) => j.status === "completed") ?? []
  const activeJobs    = jobsList?.jobs.filter((j) => j.status === "running" || j.status === "pending") ?? []

  return (
    <div className="space-y-8">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-primary">Lead Discovery</h1>
          <p className="text-sm text-secondary mt-1">
            Define your ICP, discover leads, download CSV, and send to AI scoring — all in one click.
          </p>
        </div>

        <div className="flex items-center gap-4 px-4 py-2 bg-card border border-border rounded-xl">
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wider text-secondary font-bold">Available Credits</p>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge variant="hot">{credits?.discovery_credits ?? 0} Discovery</Badge>
              <Badge variant="secondary">{credits?.enrichment_credits ?? 0} Enrichment</Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── ICP Filter Form ───────────────────────────────────────────────── */}
        <Card className="lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Filter className="size-4 text-accent" /> Target ICP
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase text-secondary">Industry</label>
              <Input
                value={filters.industry}
                onChange={(e) => setFilters({ ...filters, industry: e.target.value })}
                placeholder="e.g. SaaS, Fintech"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase text-secondary">Job Titles (Comma separated)</label>
              <Input
                value={filters.title_keywords}
                onChange={(e) => setFilters({ ...filters, title_keywords: e.target.value })}
                placeholder="e.g. VP, Director, CEO"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase text-secondary">Company Size</label>
              <Input
                value={filters.company_size}
                onChange={(e) => setFilters({ ...filters, company_size: e.target.value })}
                placeholder="e.g. 51-200, 1000+"
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-xs font-bold uppercase text-secondary">Max Leads</label>
                <span className="text-[10px] font-bold text-accent">Est. Cost: {filters.max_results} Credits</span>
              </div>
              <Input
                type="number"
                value={filters.max_results}
                onChange={(e) =>
                  setFilters({ ...filters, max_results: parseInt(e.target.value) || 0 })
                }
              />
            </div>

            {credits && credits.discovery_credits < 1 && (
              <div className="p-3 bg-accent/5 border border-accent/20 rounded-lg">
                <p className="text-[11px] text-accent font-medium leading-relaxed">
                  <AlertCircle className="inline-block mr-1 size-3 -mt-0.5" />
                  Insufficient credits. Top up your account to continue.
                </p>
              </div>
            )}

            <Button
              className="w-full mt-4"
              variant={credits && credits.discovery_credits < 1 ? "secondary" : "primary"}
              onClick={handleStartDiscovery}
              disabled={isRunning || (credits != null && credits.discovery_credits < 1)}
            >
              {isRunning ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Rocket className="mr-2 size-4" />
              )}
              {isRunning
                ? "Running Pipeline..."
                : credits && credits.discovery_credits < 1
                ? "Insufficient Balance"
                : "Initialize Discovery"}
            </Button>
          </CardContent>
        </Card>

        {/* ── Right panel ───────────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-6">

          {/* Live results after discovery */}
          {liveLeads.length > 0 && activeJobId && (
            <Card className="border-accent/30 shadow-lg shadow-accent/5">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
                <CardTitle className="flex items-center gap-2 text-accent">
                  <CheckCircle2 className="size-4" />
                  Discovery Complete — {liveLeads.length} Leads Found
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleDownloadCsv(activeJobId)}
                    disabled={downloadCsvMutation.isPending}
                    className="text-xs"
                  >
                    {downloadCsvMutation.isPending ? (
                      <Loader2 className="mr-1.5 size-3 animate-spin" />
                    ) : (
                      <Download className="mr-1.5 size-3" />
                    )}
                    Download CSV
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleSendToScoring(activeJobId)}
                    disabled={sendScoringMutation.isPending}
                    className="text-xs"
                  >
                    {sendScoringMutation.isPending ? (
                      <Loader2 className="mr-1.5 size-3 animate-spin" />
                    ) : (
                      <Brain className="mr-1.5 size-3" />
                    )}
                    Send to Scoring
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0 border-t border-border">
                <div className="overflow-auto max-h-72">
                  <Table>
                    <TableHeader className="bg-bg/50 sticky top-0">
                      <TableRow className="hover:bg-transparent border-border">
                        <TableHead className="pl-5">Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Title</TableHead>
                        <TableHead>Company</TableHead>
                        <TableHead className="text-center">Conf.</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {liveLeads.map((lead) => (
                        <TableRow key={lead.id} className="border-border hover:bg-card/50">
                          <TableCell className="pl-5 font-medium text-primary text-sm py-3">
                            {lead.full_name || "—"}
                          </TableCell>
                          <TableCell className="text-xs text-secondary font-mono">
                            {lead.email}
                          </TableCell>
                          <TableCell className="text-xs text-secondary">
                            {lead.title}
                          </TableCell>
                          <TableCell className="text-xs text-secondary">
                            {lead.company}
                          </TableCell>
                          <TableCell className="text-center">
                            <ConfBadge value={lead.identity_confidence} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Running indicator */}
          {isRunning && (
            <Card className="border-accent/20">
              <CardContent className="py-8 flex flex-col items-center gap-3 text-center">
                <div className="size-10 rounded-full border-2 border-accent border-t-transparent animate-spin" />
                <p className="text-sm font-semibold text-primary">Running 6-Stage Pipeline...</p>
                <p className="text-xs text-secondary">Discovery → Enrichment → Verification → Deduplication → Normalization → Handoff</p>
              </CardContent>
            </Card>
          )}

          {/* Active jobs */}
          {activeJobs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PlayCircle className="size-4 text-accent" /> Active Pipelines
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {activeJobs.map((job) => (
                  <div key={job.id} className="p-4 bg-bg rounded-xl border border-border space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-primary">
                            {job.input_filters?.industry} Campaign
                          </span>
                          <StatusBadge status={job.status} />
                          {job.current_stage && (
                            <Badge variant="secondary" className="text-[10px] uppercase">
                              {job.current_stage}
                            </Badge>
                          )}
                        </div>
                        <p className="text-[10px] text-secondary mt-0.5">ID: {job.id.slice(0, 8)}</p>
                      </div>
                    </div>
                    <div className="h-1.5 bg-border rounded-full overflow-hidden">
                      <div
                        className="bg-accent h-full transition-all duration-500"
                        style={{
                          width: `${Math.round(
                            ((job.processed_items ?? 0) / (job.total_items || 1)) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      {[
                        { label: "Discovered", val: job.total_raw ?? 0 },
                        { label: "Enriched", val: job.total_enriched ?? 0 },
                        { label: "Verified", val: job.success_count ?? 0 },
                      ].map(({ label, val }) => (
                        <div key={label} className="p-2 bg-card rounded-lg border border-border">
                          <p className="text-[10px] font-bold text-secondary uppercase">{label}</p>
                          <p className="text-sm font-bold text-primary">{val}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Completed jobs history */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2">
                <History className="size-4 text-secondary" /> Completed Discoveries
              </CardTitle>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => refetchJobs()}
                className="text-xs"
              >
                <RefreshCw className="mr-1.5 size-3" /> Refresh
              </Button>
            </CardHeader>
            <CardContent className="p-0 border-t border-border">
              {completedJobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <p className="text-secondary text-sm">No completed discovery jobs yet.</p>
                  <p className="text-[10px] text-secondary/60 mt-1 uppercase tracking-widest">
                    Click Initialize Discovery to get started
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader className="bg-bg/50">
                    <TableRow className="hover:bg-transparent border-border">
                      <TableHead className="pl-6">Campaign</TableHead>
                      <TableHead className="text-center">Leads</TableHead>
                      <TableHead className="text-center">Rate</TableHead>
                      <TableHead className="text-center">Status</TableHead>
                      <TableHead className="pr-6 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {completedJobs.map((job) => (
                      <TableRow key={job.id} className="border-border">
                        <TableCell className="pl-6 py-4">
                          <div className="text-sm font-medium text-primary">
                            {job.input_filters?.industry} · {job.input_filters?.company_size}
                          </div>
                          <div className="text-[10px] text-secondary font-mono mt-0.5">
                            {job.id.slice(0, 8)}
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className="font-bold text-primary text-sm">{job.total_enriched ?? 0}</span>
                          <span className="text-secondary text-xs"> / {job.total_raw ?? 0}</span>
                        </TableCell>
                        <TableCell className="text-center font-bold text-primary text-sm">
                          {Math.round((job.enrichment_rate ?? 1) * 100)}%
                        </TableCell>
                        <TableCell className="text-center">
                          <StatusBadge status={job.status} />
                        </TableCell>
                        <TableCell className="pr-6 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              size="sm"
                              variant="secondary"
                              className="text-xs h-7 px-2"
                              onClick={() => handleDownloadCsv(job.id)}
                              disabled={downloadCsvMutation.isPending}
                            >
                              <Download className="size-3 mr-1" />
                              CSV
                            </Button>
                            <Button
                              size="sm"
                              variant="primary"
                              className="text-xs h-7 px-2"
                              onClick={() => handleSendToScoring(job.id)}
                              disabled={sendScoringMutation.isPending}
                            >
                              <Brain className="size-3 mr-1" />
                              Score
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Empty state when no jobs at all */}
          {!jobsLoading && completedJobs.length === 0 && activeJobs.length === 0 && liveLeads.length === 0 && !isRunning && (
            <Card className="border-dashed">
              <CardContent className="py-16 flex flex-col items-center gap-3 text-center">
                <div className="size-12 rounded-full bg-accent/10 flex items-center justify-center">
                  <BarChart2 className="size-6 text-accent" />
                </div>
                <p className="text-primary font-semibold">Ready to find leads</p>
                <p className="text-secondary text-sm max-w-xs">
                  Configure your ICP filters and click Initialize Discovery. Results appear here instantly.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ── Previously Discovered Leads ─────────────────────────────────── */}
      {((enrichedData?.leads?.length ?? 0) > 0 || enrichedLoading) && (
        <Card className="mt-2">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="flex items-center gap-2">
              <Layers className="size-4 text-accent" />
              Previously Discovered Leads
              {enrichedData?.total != null && (
                <span className="ml-1.5 px-2 py-0.5 text-[10px] font-bold rounded-full bg-accent/15 text-accent border border-accent/25">
                  {enrichedData.total} total
                </span>
              )}
            </CardTitle>
            <Button variant="secondary" size="sm" className="text-xs" onClick={() => refetchEnriched()}>
              <RefreshCw className="mr-1.5 size-3" /> Refresh
            </Button>
          </CardHeader>
          <CardContent className="p-0 border-t border-border">
            {enrichedLoading ? (
              <div className="p-6 space-y-3">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
              </div>
            ) : (
              <>
                <div className="overflow-auto max-h-80">
                  <Table>
                    <TableHeader className="bg-bg/50 sticky top-0">
                      <TableRow className="hover:bg-transparent border-border">
                        <TableHead className="pl-5 w-[180px]">Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Title</TableHead>
                        <TableHead>Company</TableHead>
                        <TableHead>Industry</TableHead>
                        <TableHead className="text-center w-[80px]">Identity</TableHead>
                        <TableHead className="text-center w-[80px]">Email Conf.</TableHead>
                        <TableHead className="pr-5 w-[60px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {enrichedData?.leads?.map((lead: any) => {
                        const conf = lead.identity_confidence ?? 0
                        const confColor = conf >= 0.75 ? "text-green-400" : conf >= 0.5 ? "text-yellow-400" : "text-red-400"
                        const emailConf = lead.email_confidence ?? 0
                        const emailColor = emailConf >= 0.75 ? "text-green-400" : emailConf >= 0.5 ? "text-yellow-400" : "text-red-400"
                        return (
                          <TableRow key={lead.id} className="border-border hover:bg-card/50 transition-colors">
                            <TableCell className="pl-5 font-medium text-primary text-sm py-3">
                              {`${lead.first_name || ""} ${lead.last_name || ""}`.trim() || "—"}
                            </TableCell>
                            <TableCell className="text-xs text-secondary font-mono">
                              {lead.email || "—"}
                            </TableCell>
                            <TableCell className="text-xs text-secondary">{lead.title || "—"}</TableCell>
                            <TableCell className="text-xs text-secondary">{lead.company_name || "—"}</TableCell>
                            <TableCell className="text-xs text-secondary">{lead.industry || "—"}</TableCell>
                            <TableCell className="text-center">
                              <span className={`text-xs font-bold ${confColor}`}>
                                {Math.round(conf * 100)}%
                              </span>
                            </TableCell>
                            <TableCell className="text-center">
                              <span className={`text-xs font-bold ${emailColor}`}>
                                {Math.round(emailConf * 100)}%
                              </span>
                            </TableCell>
                            <TableCell className="pr-5 text-right">
                              <Button
                                size="sm" variant="secondary"
                                className="h-6 w-6 p-0 opacity-60 hover:opacity-100"
                                title="View in Leads"
                                onClick={() => router.push(`/dashboard/leads`)}
                              >
                                <ExternalLink className="size-3" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>

                {/* Enriched leads pagination */}
                {enrichedData && enrichedData.total > enrichedData.page_size && (
                  <div className="flex items-center justify-between px-5 py-3 border-t border-border">
                    <p className="text-xs text-secondary">
                      {(enrichedPage - 1) * enrichedData.page_size + 1}–{Math.min(enrichedPage * enrichedData.page_size, enrichedData.total)} of {enrichedData.total}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" size="sm" className="h-7 text-xs"
                        onClick={() => setEnrichedPage(p => Math.max(1, p - 1))}
                        disabled={enrichedPage === 1}>
                        Previous
                      </Button>
                      <Button variant="secondary" size="sm" className="h-7 text-xs"
                        onClick={() => setEnrichedPage(p => p + 1)}
                        disabled={enrichedPage >= Math.ceil(enrichedData.total / enrichedData.page_size)}>
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
