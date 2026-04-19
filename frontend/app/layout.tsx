import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

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
      <body className="bg-mesh flex min-h-full flex-col overflow-hidden [padding-bottom:var(--safe-bottom)]">
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

        <header className="fixed left-0 right-0 top-0 z-50 bg-background/60 pt-[var(--safe-top)] backdrop-blur-2xl supports-[backdrop-filter]:bg-background/30">
          <nav className="flex h-14 w-full items-center justify-between px-4 md:px-6">
            <div className="flex items-center gap-6">
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
                className="hidden text-sm text-foreground/36 transition hover:text-foreground/65 sm:block"
              >
                历史任务
              </Link>
            </div>
          </nav>
        </header>

        <ErrorBoundary>
          <div className="flex h-full flex-1 flex-col pt-[calc(var(--app-header-height)+var(--safe-top))]">
            {children}
          </div>
        </ErrorBoundary>
      </body>
    </html>
  );
}
