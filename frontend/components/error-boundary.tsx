"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

interface Props {
  children: ReactNode;
  /** Optional fallback UI — defaults to built-in error panel */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console for debugging; in production this would go to a service
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <main className="flex-1 flex items-center justify-center min-h-[50vh] px-6">
          <div className="glass-card rounded-2xl p-8 md:p-12 text-center max-w-lg space-y-5 animate-fade-in-up">
            {/* Icon */}
            <div className="w-16 h-16 mx-auto rounded-2xl bg-destructive/[0.06] flex items-center justify-center border border-destructive/15">
              <AlertTriangle className="h-7 w-7 text-destructive/60" />
            </div>

            {/* Message */}
            <div className="space-y-1.5">
              <h1 className="text-lg font-semibold">出错了</h1>
              <p className="text-sm text-muted-foreground leading-relaxed">
                页面渲染时发生了意外错误。你可以尝试刷新或返回首页。
              </p>
            </div>

            {/* Error detail (dev only) */}
            {process.env.NODE_ENV === "development" && this.state.error && (
              <details className="text-left rounded-lg border border-border/20 overflow-hidden">
                <summary className="px-4 py-2 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors bg-surface/30">
                  错误详情
                </summary>
                <pre className="px-4 py-3 text-[11px] font-mono text-red-400/80 bg-zinc-950/60 overflow-auto max-h-[200px] whitespace-pre-wrap break-all">
                  {this.state.error.message}
                  {"\n"}
                  {this.state.error.stack?.slice(0, 500)}
                </pre>
              </details>
            )}

            {/* Actions */}
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleRetry}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg btn-glow"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                重试
              </button>
              <Link
                href="/"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-border/40 text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors"
              >
                <Home className="h-3.5 w-3.5" />
                返回首页
              </Link>
            </div>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
