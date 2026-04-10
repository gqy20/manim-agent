import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { History } from "lucide-react";
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
  title: "Manim Agent — AI 数学动画生成器",
  description: "用自然语言描述数学概念，自动生成专业 Manim 动画视频",
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
      <body className="min-h-full flex flex-col bg-mesh">
        <header className="border-b border-border/50 bg-background/70 backdrop-blur-xl supports-[backdrop-filter]:bg-background/40 sticky top-0 z-50">
          <nav className="container flex h-14 items-center justify-between max-w-6xl">
            <Link href="/" className="flex items-center gap-2.5 group">
              <Logo size={26} className="text-primary" />
              <span className="font-semibold text-sm tracking-tight">
                Manim Agent
              </span>
            </Link>
            <Link
              href="/history"
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-md hover:bg-accent"
            >
              <History className="h-3.5 w-3.5" />
              历史记录
            </Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
