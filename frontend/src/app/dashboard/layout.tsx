import { AppLayout } from "@/components/layout/AppLayout"
import { ErrorBoundary } from "@/components/common/ErrorBoundary"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <AppLayout>
        {children}
      </AppLayout>
    </ErrorBoundary>
  )
}