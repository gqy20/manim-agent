import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { ErrorBoundary } from "@/components/error-boundary";
import { Logo } from "@/components/logo";
import { PageTransition } from "@/components/page-transition";
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
      <body className="bg-mesh flex h-full flex-col overflow-hidden [padding-bottom:var(--safe-bottom)]">
        <div className="pointer-events-none fixed inset-0 z-[1] h-full w-full opacity-[0.03] mix-blend-overlay">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
            <filter id="noise">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.8"
                numOctaves="4"
                stitchTiles="stitch"
              />
            </filter>
            <rect width="100%" height="100%" filter="url(#noise)" />
          </svg>
        </div>

        <header className="fixed left-0 right-0 top-0 z-50 bg-background/55 pt-[var(--safe-top)] backdrop-blur-2xl supports-[backdrop-filter]:bg-background/28">
          <nav className="flex h-14 w-full items-center justify-between px-4 md:px-6">
            <div className="flex items-center gap-7">
              <Link href="/create" className="group flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-primary/18 bg-primary/[0.045] text-primary transition-transform duration-300 group-hover:rotate-12">
                  <Logo size={22} />
                </span>
                <span className="text-sm font-semibold tracking-tight transition-colors group-hover:text-foreground">
                  Manim Agent
                </span>
              </Link>
              <div className="hidden items-center gap-5 sm:flex">
                <Link
                  href="/create"
                  className="text-sm text-foreground/72 transition hover:text-foreground"
                >
                  创建
                </Link>
                <Link
                  href="/history"
                  className="text-sm text-foreground/38 transition hover:text-foreground/68"
                >
                  历史
                </Link>
              </div>
            </div>
            <span className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.025] px-2.5 py-1.5 text-xs text-foreground/42">
              <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_12px_oklch(0.72_0.11_250/0.8)]" />
              Ready
            </span>
          </nav>
        </header>

        <ErrorBoundary>
          <PageTransition>
            <div className="flex h-full min-h-0 flex-1 flex-col overflow-y-auto pt-[calc(var(--app-header-height)+var(--safe-top))]">
              {children}
            </div>
          </PageTransition>
        </ErrorBoundary>
      </body>
    </html>
  );
}
