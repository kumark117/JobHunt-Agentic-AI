import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { VersionBadge } from "@/components/VersionBadge";

export const metadata: Metadata = {
  title: "JobHunt Agent",
  description: "Automated job hunt with human-in-the-loop control",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50">
        <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6">
          <Link href="/" className="font-semibold text-slate-900 hover:text-brand-600">
            JobHunt Agent
          </Link>
          <Link href="/" className="text-sm text-slate-600 hover:text-slate-900">
            Pipeline
          </Link>
          <Link href="/settings" className="text-sm text-slate-600 hover:text-slate-900">
            Settings
          </Link>
          <VersionBadge />
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
