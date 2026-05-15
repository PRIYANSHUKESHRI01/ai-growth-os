import { LucideIcon } from "lucide-react"

interface EmptyStateProps {
  title: string
  description: string
  action?: React.ReactNode
  icon: LucideIcon
}

export function EmptyState({ title, description, action, icon: Icon }: EmptyStateProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/50 px-6 py-10 text-center transition-all">
      <div className="flex size-14 items-center justify-center rounded-full bg-bg mb-4">
        <Icon className="size-6 text-secondary" />
      </div>
      <h3 className="mb-2 text-xl font-semibold text-primary">{title}</h3>
      <p className="mb-6 max-w-sm text-sm text-secondary">{description}</p>
      {action && <div>{action}</div>}
    </div>
  )
}
