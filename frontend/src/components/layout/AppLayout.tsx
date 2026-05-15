import { Sidebar } from "./Sidebar"

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <main className="pl-64">
        <div className="mx-auto max-w-7xl px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}
