import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { History, Sparkles, Command } from "lucide-react";
import { Logo } from "@/components/logo";
import { ErrorBoundary } from "@/components/error-boundary";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Manim Agent — AI 数学动画生成器",
  description: "用自然语言描述数学概念，自动生成专业 Manim 动画视频",
};

/* ── Footer ─────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border/40 bg-background/50 backdrop-blur-sm">
      <div className="w-full px-6 md:px-10 py-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
            <Logo size={18} className="text-primary/60" />
            <span>Manim Agent</span>
            <span className="text-border">·</span>
            <span className="text-xs text-muted-foreground/50">AI 数学动画生成器</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-5 text-xs text-muted-foreground/60">
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-border/30">
              <Command className="h-3 w-3" />
              Powered by Manim + AI
            </span>
          </div>

          {/* Copyright */}
          <p className="text-[11px] text-muted-foreground/40">
            &copy; {new Date().getFullYear()} Manim Agent
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ── Layout ─────────────────────────────────────── */

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-mesh">
        {/* Header */}
        <header className="border-b border-border/40 bg-background/60 backdrop-blur-2xl supports-[backdrop-filter]:bg-background/30 sticky top-0 z-50">
          <nav className="w-full px-6 md:px-10 flex h-14 items-center justify-between">
            {/* Left: Brand */}
            <Link href="/" className="flex items-center gap-2.5 group">
              <Logo size={24} className="text-primary transition-transform duration-300 group-hover:rotate-12" />
              <div className="flex flex-col leading-none">
                <span className="font-semibold text-sm tracking-tight group-hover:text-foreground transition-colors">
                  Manim Agent
                </span>
                <span className="text-[10px] text-muted-foreground/50 tracking-wide hidden sm:block">
                  AI Math Animator
                </span>
              </div>
            </Link>

            {/* Right: Actions */}
            <div className="flex items-center gap-1">
              <Link
                href="/history"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-all duration-200 px-3 py-1.5 rounded-lg hover:bg-accent/50 group"
              >
                <History className="h-3.5 w-3.5 group-hover:text-primary/70 transition-colors" />
                <span className="hidden sm:inline">历史记录</span>
              </Link>
              <div className="w-px h-4 bg-border/50 mx-1 hidden sm:block" />
              <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/35 px-2 py-0.5 rounded-full bg-surface/50 border border-border/20">
                <Sparkles className="h-2.5 w-2.5" />
                v0.1
              </span>
            </div>
          </nav>
        </header>

        {/* Page content */}
        <ErrorBoundary>{children}</ErrorBoundary>

        {/* Footer */}
        <Footer />
      </body>
    </html>
  );
}
