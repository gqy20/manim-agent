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
  title: "Manim Agent",
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
      <body className="bg-mesh flex min-h-full flex-col [padding-bottom:var(--safe-bottom)]">
        {/* SVG Noise Texture Overlay */}
        <div className="pointer-events-none fixed inset-0 z-[1] h-full w-full opacity-[0.03] mix-blend-overlay">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
            <filter id="noise">
              <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch" />
            </filter>
            <rect width="100%" height="100%" filter="url(#noise)" />
          </svg>
        </div>
        
        <header className="fixed left-0 right-0 top-0 z-50 bg-background/60 pt-[var(--safe-top)] backdrop-blur-2xl supports-[backdrop-filter]:bg-background/30">
          <nav className="flex h-14 w-full items-center justify-between px-4 md:px-6">
            <Link href="/" className="group flex items-center gap-2.5">
              <Logo
                size={24}
                className="text-primary transition-transform duration-300 group-hover:rotate-12"
              />
              <div className="flex flex-col leading-none">
                <span className="text-sm font-semibold tracking-tight transition-colors group-hover:text-foreground">
                  Manim Agent
                </span>
              </div>
            </Link>

            <Link
              href="/history"
              className="group flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-all duration-200 hover:bg-accent/50 hover:text-foreground"
            >
              <History className="h-3.5 w-3.5 transition-colors group-hover:text-primary/70" />
              <span className="hidden sm:inline">历史记录</span>
            </Link>
          </nav>
        </header>

        <ErrorBoundary>
          <div className="flex flex-1 flex-col pt-[calc(var(--app-header-height)+var(--safe-top))]">
            {children}
          </div>
        </ErrorBoundary>
      </body>
    </html>
  );
}
