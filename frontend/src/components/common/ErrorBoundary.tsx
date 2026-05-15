"use client"

import React, { Component, ErrorInfo, ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { AlertCircle, RefreshCw } from "lucide-react"

interface Props {
  children?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
    window.location.href = "/dashboard"
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center space-y-6">
          <div className="size-16 rounded-full bg-accent/10 flex items-center justify-center">
            <AlertCircle className="size-8 text-accent" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-primary">Intelligence Engine Stalled</h2>
            <p className="text-secondary max-w-md mx-auto">
              We encountered an unexpected error while processing your growth intelligence. This has been logged and we are looking into it.
            </p>
          </div>
          {this.state.error && (
            <pre className="p-4 bg-bg border border-border rounded-lg text-xs text-secondary max-w-full overflow-auto font-mono">
              {this.state.error.message}
            </pre>
          )}
          <Button variant="primary" onClick={this.handleReset}>
            <RefreshCw className="mr-2 size-4" /> Reset Application
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
