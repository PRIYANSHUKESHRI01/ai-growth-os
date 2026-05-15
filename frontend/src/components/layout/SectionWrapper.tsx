import * as React from "react"
import { cn } from "@/lib/utils"

interface SectionWrapperProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode
}

export function SectionWrapper({ children, className, ...props }: SectionWrapperProps) {
  return (
    <section className={cn("max-w-6xl mx-auto px-6 py-20", className)} {...props}>
      {children}
    </section>
  )
}
