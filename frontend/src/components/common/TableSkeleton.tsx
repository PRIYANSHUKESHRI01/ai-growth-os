import { Skeleton } from "@/components/ui/skeleton"

export function TableSkeleton() {
  return (
    <div className="w-full rounded-xl border border-border overflow-hidden">
      <div className="border-b border-border bg-bg p-4 flex gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-5 w-1/4 flex-1" />
        ))}
      </div>
      <div className="bg-card">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-4 border-b border-border p-4 last:border-0 hover:bg-bg/50 transition-colors">
            {Array.from({ length: 4 }).map((_, j) => (
              <Skeleton key={j} className="h-4 w-1/4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
