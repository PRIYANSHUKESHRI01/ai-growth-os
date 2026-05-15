"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow
} from "@/components/ui/table"
import {
  Search, Filter, Download, Plus, Loader2, Brain,
  Zap, CheckCircle2, Sparkles, Trash2, AlertTriangle
} from "lucide-react"
import { useRouter } from "next/navigation"
import {
  useLeads, useUploadLeads, useScoreAllLeads,
  useScoreLead, useDeleteLead
} from "@/hooks/useLeads"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"

// ── Helpers ───────────────────────────────────────────────────────────────────
function scoreColor(score: number) {
  if (score >= 0.8) return "text-green-400"
  if (score >= 0.55) return "text-yellow-400"
  return "text-red-400"
}

function tagVariant(tag?: string): "hot" | "warm" | "cold" | "secondary" {
  const t = (tag ?? "").toLowerCase()
  if (t.includes("hot"))  return "hot"
  if (t.includes("warm")) return "warm"
  if (t.includes("cold")) return "cold"
  return "secondary"
}

// ── Score button (hover-reveal, only on unscored rows) ────────────────────────
function ScoreButton({ leadId, onDone }: { leadId: string; onDone?: () => void }) {
  const scoreOne = useScoreLead()
  const isScoring = scoreOne.isPending && scoreOne.variables === leadId

  return (
    <Button
      size="sm" variant="secondary"
      className="h-7 px-2.5 text-[11px] font-semibold gap-1.5"
      onClick={(e) => {
        e.stopPropagation()
        scoreOne.mutate(leadId, {
          onSuccess: (d) => {
            toast.success(d.message || "Lead scored!", {
              description: `${Math.round(d.final_score * 100)} · ${d.tag}`,
            })
            onDone?.()
          },
          onError: (err: any) => toast.error(err?.message || "Scoring failed."),
        })
      }}
      disabled={isScoring}
    >
      {isScoring ? <Loader2 className="size-3 animate-spin" /> : <Brain className="size-3" />}
      {isScoring ? "Scoring…" : "Score"}
    </Button>
  )
}

// ── Delete button with inline confirmation ────────────────────────────────────
function DeleteButton({ leadId, leadName }: { leadId: string; leadName: string }) {
  const [confirming, setConfirming] = useState(false)
  const deleteMutation = useDeleteLead()
  const isDeleting = deleteMutation.isPending && deleteMutation.variables === leadId

  if (confirming) {
    return (
      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        <span className="text-[10px] text-red-400 font-semibold whitespace-nowrap">Delete?</span>
        <Button
          size="sm" variant="destructive"
          className="h-6 px-2 text-[10px] font-bold bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30"
          disabled={isDeleting}
          onClick={(e) => {
            e.stopPropagation()
            deleteMutation.mutate(leadId, {
              onSuccess: () => toast.success(`"${leadName}" deleted.`),
              onError: (err: any) => toast.error(err?.message || "Delete failed."),
            })
            setConfirming(false)
          }}
        >
          {isDeleting ? <Loader2 className="size-2.5 animate-spin" /> : "Yes"}
        </Button>
        <Button
          size="sm" variant="secondary"
          className="h-6 px-2 text-[10px]"
          onClick={(e) => { e.stopPropagation(); setConfirming(false) }}
        >
          No
        </Button>
      </div>
    )
  }

  return (
    <Button
      size="sm" variant="secondary"
      className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity text-secondary hover:text-red-400 hover:bg-red-500/10"
      onClick={(e) => { e.stopPropagation(); setConfirming(true) }}
      disabled={isDeleting}
      title="Delete lead"
    >
      <Trash2 className="size-3.5" />
    </Button>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LeadsPage() {
  const router = useRouter()
  const [page, setPage] = useState(1)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading, refetch } = useLeads(page)
  const uploadMutation   = useUploadLeads()
  const scoreAllMutation = useScoreAllLeads()

  const leads         = data?.leads ?? []
  const unscoredCount = leads.filter(l => !l.score).length
  const scoredCount   = leads.filter(l => !!l.score).length
  const isScoring     = scoreAllMutation.isPending

  const handleScoreAll = () => {
    if (unscoredCount === 0) { toast.info("All leads are already scored."); return }
    toast.loading(`Scoring ${unscoredCount} unscored leads…`, { id: "score-all" })
    scoreAllMutation.mutate(undefined, {
      onSuccess: (d) => {
        toast.success(d.message || `Scored ${d.scored} leads!`, { id: "score-all" })
        refetch()
      },
      onError: (err: any) => toast.error(err?.message || "Scoring failed.", { id: "score-all" }),
    })
  }

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-primary">Lead Scoring</h1>
          <p className="text-sm text-secondary mt-1">
            AI-powered lead intelligence. Score, review, and manage your pipeline.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm">
            <Download className="mr-2 size-4" /> Export
          </Button>
          <input type="file" ref={fileInputRef} onChange={e => {
            const f = e.target.files?.[0]; if (f) uploadMutation.mutate(f)
          }} className="hidden" accept=".csv" />
          <Button variant="secondary" size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending
              ? <Loader2 className="mr-2 size-4 animate-spin" />
              : <Plus className="mr-2 size-4" />}
            Add Leads
          </Button>
        </div>
      </div>

      {/* ── Stats + Score-All bar ───────────────────────────────────────────── */}
      {!isLoading && leads.length > 0 && (
        <div className="flex items-center gap-4 p-4 bg-card border border-border rounded-xl">
          <div className="flex items-center gap-3 flex-1">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-lg">
              <CheckCircle2 className="size-3.5 text-green-400" />
              <span className="text-xs font-bold text-green-400">{scoredCount} scored</span>
            </div>
            {unscoredCount > 0 ? (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                <Zap className="size-3.5 text-yellow-400" />
                <span className="text-xs font-bold text-yellow-400">{unscoredCount} unscored</span>
              </div>
            ) : (
              <span className="text-xs text-secondary italic">All leads are scored ✓</span>
            )}
            <span className="text-xs text-secondary/50 ml-1">
              {data?.total ?? 0} total
            </span>
          </div>
          {unscoredCount > 0 && (
            <Button variant="primary" size="sm" onClick={handleScoreAll} disabled={isScoring} className="shrink-0">
              {isScoring
                ? <Loader2 className="mr-2 size-4 animate-spin" />
                : <Sparkles className="mr-2 size-4" />}
              {isScoring ? `Scoring…` : `Score All Unscored (${unscoredCount})`}
            </Button>
          )}
        </div>
      )}

      {/* ── Scoring progress banner ─────────────────────────────────────────── */}
      {isScoring && (
        <div className="flex items-center gap-3 px-4 py-3 bg-accent/8 border border-accent/25 rounded-xl">
          <div className="size-6 rounded-full border-2 border-accent border-t-transparent animate-spin shrink-0" />
          <div>
            <p className="text-sm font-semibold text-accent">AI Scoring Engine Running</p>
            <p className="text-xs text-secondary">Analyzing signals · computing scores · building intelligence profiles…</p>
          </div>
        </div>
      )}

      {/* ── Search ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-secondary" />
          <Input placeholder="Search leads…" className="pl-9 h-10 bg-card" />
        </div>
        <Button variant="secondary" size="icon" className="h-10 w-10 shrink-0">
          <Filter className="size-4" />
        </Button>
      </div>

      {/* ── Table ──────────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-3">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : leads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="size-14 rounded-full bg-accent/10 flex items-center justify-center mb-4">
              <Zap className="size-7 text-accent" />
            </div>
            <p className="text-lg font-bold text-primary">No leads in pipeline yet</p>
            <p className="text-sm text-secondary max-w-xs mt-1 mb-6">
              Discover new leads or upload your own CSV to get started.
            </p>
            <div className="flex items-center gap-3">
              <Button variant="secondary" size="sm" onClick={() => router.push("/dashboard/discovery")}>
                <Search className="mr-2 size-4" /> Discovery
              </Button>
              <Button variant="primary" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Plus className="mr-2 size-4" /> Add Leads
              </Button>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-bg/50">
              <TableRow className="hover:bg-transparent border-border">
                <TableHead className="pl-6 w-[200px]">Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="text-center w-[80px]">Score</TableHead>
                <TableHead className="text-center w-[110px]">Tag</TableHead>
                {/* Actions column: Score (unscored) | ✓ (scored) + Delete */}
                <TableHead className="pr-4 w-[130px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.map((lead) => {
                const isScored   = !!lead.score
                const finalScore = lead.score?.final_score ?? null
                const tag        = lead.score?.tag
                const name = `${lead.first_name || ""} ${lead.last_name || ""}`.trim() || "Unknown"

                return (
                  <TableRow
                    key={lead.id}
                    className="group cursor-pointer hover:bg-bg/60 transition-colors border-border"
                    onClick={() => router.push(`/dashboard/leads/${lead.id}`)}
                  >
                    <TableCell className="pl-6 font-medium text-primary py-4">{name}</TableCell>
                    <TableCell className="text-secondary text-sm font-mono">{lead.email}</TableCell>
                    <TableCell className="text-secondary text-sm">{lead.company || "—"}</TableCell>
                    <TableCell className="text-secondary text-sm">{(lead as any).title || "—"}</TableCell>

                    {/* Score */}
                    <TableCell className="text-center">
                      {isScored && finalScore !== null ? (
                        <span className={`font-bold text-sm tabular-nums ${scoreColor(finalScore)}`}>
                          {Math.round(finalScore * 100)}
                        </span>
                      ) : (
                        <span className="text-secondary/40 text-xs">—</span>
                      )}
                    </TableCell>

                    {/* Tag */}
                    <TableCell className="text-center">
                      {isScored ? (
                        <Badge variant={tagVariant(tag)}>{tag || "SCORED"}</Badge>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-border/60 text-secondary/60 border border-border">
                          UNSCORED
                        </span>
                      )}
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="pr-4">
                      <div
                        className="flex items-center justify-end gap-1.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {/* Score button — only on unscored, hidden until row hover */}
                        {!isScored && (
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                            <ScoreButton leadId={lead.id} onDone={() => refetch()} />
                          </div>
                        )}
                        {/* Scored indicator — subtle on hover */}
                        {isScored && (
                          <CheckCircle2 className="size-4 text-green-500/40 opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                        {/* Delete — always in the row, visible on hover */}
                        <DeleteButton leadId={lead.id} leadName={name} />
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </div>

      {/* ── Pagination ─────────────────────────────────────────────────────── */}
      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between py-2">
          <p className="text-xs text-secondary">
            Showing {(page - 1) * data.page_size + 1}–{Math.min(page * data.page_size, data.total)} of {data.total} leads
          </p>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              Previous
            </Button>
            <span className="text-sm text-secondary px-1">
              {page} / {Math.ceil(data.total / data.page_size)}
            </span>
            <Button variant="secondary" size="sm"
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil(data.total / data.page_size)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}