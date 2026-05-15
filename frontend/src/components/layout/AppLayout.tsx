"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import Image from "next/image";
import { Sidebar } from "./Sidebar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpen] = useState(true);

  return (
    <div className="min-h-screen bg-bg flex">
      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <Sidebar
        mobileOpen={mobileOpen}
        desktopOpen={desktopOpen}
        onMobileClose={() => setMobileOpen(false)}
        onDesktopToggle={() => setDesktopOpen((v) => !v)}
      />

      {/* ── Right side ───────────────────────────────────────────────────── */}
      <div
        className={[
          "flex-1 flex flex-col min-w-0 transition-all duration-300",
          desktopOpen ? "lg:ml-64" : "lg:ml-0",
        ].join(" ")}
      >
        {/*
         * ── Topbar ──────────────────────────────────────────────────────
         *
         * PRODUCTION DECISION (10M SaaS standard — Linear, Notion, Vercel):
         *   Desktop: sidebar is visible → topbar shows only the hamburger
         *            toggle (when sidebar closed) + right-side actions.
         *            Brand is NOT duplicated here.
         *   Mobile:  sidebar is hidden → topbar shows hamburger + brand
         *            so users always know where they are.
         */}
        <header className="sticky top-0 z-30 h-14 bg-card border-b border-border flex items-center px-4 gap-3 shrink-0 relative">

          {/* Mobile: hamburger + brand (sidebar is hidden) */}
          <div className="flex items-center gap-2.5 lg:hidden">
            <button
              onClick={() => setMobileOpen(true)}
              className="p-2 rounded-lg text-secondary hover:text-primary hover:bg-bg/60 transition-colors -ml-1"
              aria-label="Open navigation menu"
            >
              <Menu className="size-5" />
            </button>
            {/* Brand shown only on mobile */}
            <div className="flex items-center gap-2">
              <Image
                src="/logo.png"
                alt="AI Growth OS"
                width={36}
                height={36}
                className="object-contain shrink-0"
                priority
              />
              <span className="font-bold text-sm text-primary tracking-tight">AI Growth OS</span>
            </div>
          </div>

          {/* Desktop: only show re-open button when sidebar is collapsed */}
          {!desktopOpen && (
            <button
              onClick={() => setDesktopOpen(true)}
              className="hidden lg:flex p-2 rounded-lg text-secondary hover:text-primary hover:bg-bg/60 transition-colors -ml-1"
              aria-label="Open sidebar"
            >
              <Menu className="size-5" />
            </button>
          )}

          {/* DESKTOP nav links — absolutely centered in topbar */}
          <div className="hidden lg:flex items-center gap-6 absolute left-1/2 -translate-x-1/2">
            {["Platform", "Solutions", "Resources", "Pricing"].map((label) => (
              <span
                key={label}
                className="text-sm font-medium text-secondary cursor-default select-none"
              >
                {label}
              </span>
            ))}
          </div>

          {/* Spacer */}
          <div className="flex-1" />
        </header>

        {/* ── Page content ─────────────────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
