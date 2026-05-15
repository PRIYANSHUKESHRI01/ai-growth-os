"use client";

import Image from "next/image";
import {
  LayoutDashboard,
  Users,
  Zap,
  Megaphone,
  BarChart3,
  GitMerge,
  Settings,
  HelpCircle,
  LifeBuoy,
  LogOut,
  PanelLeftClose,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import clsx from "clsx";
import { useDiscoveryCredits } from "@/hooks/useDiscovery";
import { useUser, useClerk } from "@clerk/nextjs";

// ── Navigation config ─────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard",           devLabel: "" },
  { icon: Zap,             label: "Discovery", href: "/dashboard/discovery", devLabel: "lead_discovery" },
  { icon: Users,           label: "Leads",     href: "/dashboard/leads",     devLabel: "lead_scoring" },
  { icon: Megaphone,       label: "Campaigns", href: "/dashboard/campaigns", devLabel: "outreach_engine" },
  { icon: BarChart3,       label: "Analytics", href: "/dashboard/analytics", devLabel: "" },
  { icon: GitMerge,        label: "Workflows", href: "/dashboard/workflows", devLabel: "" },
];

const UTILITY_NAV_ITEMS = [
  { icon: Settings,   label: "Settings", href: "/dashboard/settings" },
  { icon: LifeBuoy,   label: "Support",  href: "/dashboard/support" },
  { icon: HelpCircle, label: "Help",     href: "/dashboard/help" },
];

// ── Props ─────────────────────────────────────────────────────────────────────
interface SidebarProps {
  /** Mobile: is the overlay-drawer open? */
  mobileOpen: boolean;
  /** Desktop: is the side-panel visible? */
  desktopOpen: boolean;
  onMobileClose: () => void;
  onDesktopToggle: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function Sidebar({
  mobileOpen,
  desktopOpen,
  onMobileClose,
  onDesktopToggle,
}: SidebarProps) {
  const pathname = usePathname();
  const { user } = useUser();
  const { signOut } = useClerk();

  // Display name
  const displayName =
    user?.fullName ||
    `${user?.firstName || ""} ${user?.lastName || ""}`.trim() ||
    user?.primaryEmailAddress?.emailAddress?.split("@")[0] ||
    "User";

  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  // ESC closes mobile drawer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileOpen) onMobileClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [mobileOpen, onMobileClose]);

  // Prevent body scroll when mobile drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const isActive = (href: string) =>
    href === "/dashboard"
      ? pathname === "/dashboard"
      : pathname === href || pathname.startsWith(href + "/");

  // Close mobile drawer on nav click
  const handleNav = () => onMobileClose();

  // Shared panel JSX — rendered once, controlled by CSS transforms
  const panel = (
    <aside className="w-64 h-full bg-card flex flex-col border-r border-border overflow-hidden">
      {/* ── Header: logo + close ──────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 shrink-0">
        {/* Logo mark + wordmark */}
        <div className="flex items-center gap-3 min-w-0">
          {/* No container/border — logo rendered directly, premium SaaS standard */}
          <Image
            src="/logo.png"
            alt="AI Growth OS"
            width={40}
            height={40}
            className="object-contain shrink-0"
            priority
          />
          <div className="min-w-0">
            <h2 className="font-bold text-sm text-primary leading-tight truncate">AI Growth OS</h2>
            <p className="text-[9px] font-semibold text-secondary/60 tracking-widest uppercase leading-tight">
              Premium Growth
            </p>
          </div>
        </div>
        {/* Desktop close: calls desktopToggle | Mobile close: calls mobileClose */}
        <button
          className="p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-bg/70 transition-colors"
          onClick={() => {
            onMobileClose();      // always close mobile if open
            onDesktopToggle();    // always toggle desktop
          }}
          aria-label="Toggle sidebar"
          title="Close sidebar"
        >
          <PanelLeftClose className="size-4" />
        </button>
      </div>

      {/* ── Scrollable nav area ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-3 space-y-0.5 flex flex-col">
        {/* Main nav */}
        <nav className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                onClick={handleNav}
                title={item.devLabel ? `Module: ${item.devLabel}` : item.label}
                className={clsx(
                  "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  active
                    ? "bg-bg text-primary shadow-sm"
                    : "text-secondary hover:text-primary hover:bg-bg/60"
                )}
              >
                <item.icon
                  className={clsx(
                    "size-4 shrink-0 transition-transform group-hover:scale-110",
                    active ? "text-accent" : ""
                  )}
                />
                <span className="flex-1 truncate">{item.label}</span>
                {item.devLabel && (
                  <span className="text-[9px] text-secondary/30 font-mono hidden group-hover:inline truncate max-w-[60px]">
                    {item.devLabel}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Divider */}
        <div className="border-t border-border/50 my-2 mx-1" />

        {/* Utility nav: Settings / Support / Help */}
        <nav className="space-y-0.5">
          {UTILITY_NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                onClick={handleNav}
                className={clsx(
                  "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  active
                    ? "bg-bg text-primary shadow-sm"
                    : "text-secondary hover:text-primary hover:bg-bg/60"
                )}
              >
                <item.icon
                  className={clsx(
                    "size-4 shrink-0 transition-transform group-hover:scale-110",
                    active ? "text-accent" : ""
                  )}
                />
                <span className="flex-1 truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Spacer pushes profile to bottom */}
        <div className="flex-1" />
      </div>

      {/* ── User + Sign out + Credits ─────────────────────────────────── */}
      <div className="border-t border-border px-3 py-3 shrink-0 space-y-1">
        {/* User row */}
        <div className="flex items-center gap-3 px-2 py-1.5">
          <div className="size-8 rounded-full bg-accent/10 flex items-center justify-center text-accent font-bold text-sm shrink-0 overflow-hidden">
            {user?.imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.imageUrl} alt={displayName} className="size-8 object-cover" />
            ) : (
              initials
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-primary truncate leading-tight">{displayName}</p>
            <p className="text-[11px] text-secondary truncate leading-tight mt-0.5">
              {user?.primaryEmailAddress?.emailAddress || ""}
            </p>
          </div>
        </div>

        {/* Sign out */}
        <button
          onClick={() => signOut({ redirectUrl: "/" })}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-secondary hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut className="size-4 shrink-0" />
          Sign Out
        </button>

        {/* Credits */}
        <CreditIndicator />
      </div>
    </aside>
  );

  return (
    <>
      {/* ── MOBILE: overlay drawer ─────────────────────────────────────────── */}
      {/* Backdrop */}
      <div
        className={clsx(
          "lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300",
          mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onMobileClose}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div
        className={clsx(
          "lg:hidden fixed inset-y-0 left-0 z-50 w-64 transition-transform duration-300 ease-in-out shadow-2xl",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {panel}
      </div>

      {/* ── DESKTOP: static side panel ──────────────────────────────────────── */}
      <div
        className={clsx(
          "hidden lg:block fixed inset-y-0 left-0 z-50 w-64 transition-transform duration-300 ease-in-out",
          desktopOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {panel}
      </div>
    </>
  );
}

// ── Credit indicator ──────────────────────────────────────────────────────────
function CreditIndicator() {
  const { data: credits } = useDiscoveryCredits();
  const isLow =
    (credits?.discovery_credits ?? 99) < 3 ||
    (credits?.enrichment_credits ?? 99) < 3;

  return (
    <div
      className={clsx(
        "mt-1 p-3 border rounded-xl",
        isLow ? "bg-red-500/10 border-red-500/30" : "bg-bg border-border"
      )}
    >
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[10px] font-bold text-secondary uppercase tracking-wider">Balance</p>
        <span className={clsx("text-[10px] font-bold", isLow ? "text-red-400" : "text-accent")}>
          {isLow ? "Low" : "Active"}
        </span>
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Discovery</span>
          <span className={clsx("font-bold tabular-nums", (credits?.discovery_credits ?? 99) < 3 ? "text-red-400" : "text-primary")}>
            {credits?.discovery_credits ?? 0}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Enrichment</span>
          <span className={clsx("font-bold tabular-nums", (credits?.enrichment_credits ?? 99) < 3 ? "text-red-400" : "text-primary")}>
            {credits?.enrichment_credits ?? 0}
          </span>
        </div>
      </div>
    </div>
  );
}
