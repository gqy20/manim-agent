import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Command, History, Sparkles } from "lucide-react";
import { ErrorBoundary } from "@/components/error-boundary";
import { Logo } from "@/components/logo";
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
  title: "Manim Agent - AI 数学动画生成器",
  description: "用自然语言描述数学概念，自动生成带讲解的 Manim 动画视频。",
};

function Footer() {
  return (
    <footer className="border-t border-border/40 bg-background/50 backdrop-blur-sm">
      <div className="w-full px-6 py-8 md:px-10">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
            <Logo size={18} className="text-primary/60" />
            <span>Manim Agent</span>
            <span className="text-border">·</span>
            <span className="text-xs text-muted-foreground/50">AI 数学动画生成器</span>
          </div>

          <div className="flex items-center gap-5 text-xs text-muted-foreground/60">
            <span className="hidden items-center gap-1.5 rounded-full border border-border/30 bg-surface px-2.5 py-1 sm:inline-flex">
              <Command className="h-3 w-3" />
              Powered by Manim + AI
            </span>
          </div>

          <p className="text-[11px] text-muted-foreground/40">
            &copy; {new Date().getFullYear()} Manim Agent
          </p>
        </div>
      </div>
    </footer>
  );
}

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
      <body className="bg-mesh flex min-h-full flex-col">
        <header className="sticky top-0 z-50 border-b border-border/40 bg-background/60 backdrop-blur-2xl supports-[backdrop-filter]:bg-background/30">
          <nav className="flex h-14 w-full items-center justify-between px-6 md:px-10">
            <Link href="/" className="group flex items-center gap-2.5">
              <Logo
                size={24}
                className="text-primary transition-transform duration-300 group-hover:rotate-12"
              />
              <div className="flex flex-col leading-none">
                <span className="text-sm font-semibold tracking-tight transition-colors group-hover:text-foreground">
                  Manim Agent
                </span>
                <span className="hidden text-[10px] tracking-wide text-muted-foreground/50 sm:block">
                  AI Math Animator
                </span>
              </div>
            </Link>

            <div className="flex items-center gap-1">
              <Link
                href="/history"
                className="group flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-all duration-200 hover:bg-accent/50 hover:text-foreground"
              >
                <History className="h-3.5 w-3.5 transition-colors group-hover:text-primary/70" />
                <span className="hidden sm:inline">历史记录</span>
              </Link>
              <div className="mx-1 hidden h-4 w-px bg-border/50 sm:block" />
              <span className="inline-flex items-center gap-1 rounded-full border border-border/20 bg-surface/50 px-2 py-0.5 text-[10px] text-muted-foreground/35">
                <Sparkles className="h-2.5 w-2.5" />
                v0.1
              </span>
            </div>
          </nav>
        </header>

        <ErrorBoundary>{children}</ErrorBoundary>
        <Footer />
      </body>
    </html>
  );
}
