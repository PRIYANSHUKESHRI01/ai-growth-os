"use client";
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
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useDiscoveryCredits } from "@/hooks/useDiscovery";
import { useUser, useClerk } from "@clerk/nextjs";

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", devLabel: "" },
  { icon: Zap, label: "Discovery", href: "/dashboard/discovery", devLabel: "lead_discovery" },
  { icon: Users, label: "Leads", href: "/dashboard/leads", devLabel: "lead_scoring" },
  { icon: Megaphone, label: "Campaigns", href: "/dashboard/campaigns", devLabel: "outreach_engine" },
  { icon: BarChart3, label: "Analytics", href: "/dashboard/analytics", devLabel: "" },
  { icon: GitMerge, label: "Workflows", href: "/dashboard/workflows", devLabel: "" },
];

const BOTTOM_ITEMS = [
  { icon: Settings, label: "Settings", href: "/dashboard/settings" },
  { icon: LifeBuoy, label: "Support", href: "/dashboard/support" },
  { icon: HelpCircle, label: "Help", href: "/dashboard/help" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const { signOut } = useClerk();

  // Build display name from Clerk user
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

  return (
    <div className="w-64 border-r border-border h-screen fixed left-0 top-0 bg-card flex flex-col">
      <div className="p-6">
        <h2 className="font-bold text-lg text-primary">AI Growth OS</h2>
        <p className="text-xs font-medium text-secondary mt-1 tracking-wide uppercase">
          Premium Growth
        </p>
      </div>

      <div className="px-4 flex-1 space-y-1 mt-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.label}
              href={item.href}
              title={item.devLabel ? `Automation: ${item.devLabel}` : item.label}
              className={clsx(
                "group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-bg text-primary shadow-sm"
                  : "text-secondary hover:text-primary hover:bg-bg/50"
              )}
            >
              <item.icon
                className={clsx("size-4 transition-transform group-hover:scale-110", isActive ? "text-accent" : "")}
              />
              <span className="flex-1">{item.label}</span>
              {item.devLabel && (
                <span className="text-[9px] text-secondary/40 font-mono hidden group-hover:inline">
                  {item.devLabel}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      <div className="px-4 pb-6 space-y-1">
        {BOTTOM_ITEMS.map((item) => {
          return (
            <Link
              key={item.label}
              href={item.href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-secondary hover:text-primary hover:bg-bg/50 transition-colors"
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}

        {/* Real user identity from Clerk */}
        <div className="mt-8 pt-6 border-t border-border px-3 flex items-center gap-3">
          <div className="size-9 rounded-full bg-accent/10 flex items-center justify-center text-accent font-bold text-sm shrink-0">
            {user?.imageUrl ? (
              <img
                src={user.imageUrl}
                alt={displayName}
                className="size-9 rounded-full object-cover"
              />
            ) : (
              initials
            )}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-primary truncate">
              {displayName}
            </p>
            <p className="text-xs text-secondary mt-0.5 truncate">
              {user?.primaryEmailAddress?.emailAddress || ""}
            </p>
          </div>
        </div>

        {/* Sign out */}
        <button
          onClick={() => signOut({ redirectUrl: "/" })}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-secondary hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <LogOut className="size-4" />
          Sign Out
        </button>

        <CreditIndicator />
      </div>
    </div>
  );
}

function CreditIndicator() {
  const { data: credits } = useDiscoveryCredits();

  const isLow =
    (credits?.discovery_credits ?? 99) < 3 ||
    (credits?.enrichment_credits ?? 99) < 3;

  return (
    <div
      className={clsx(
        "mt-4 p-3 border rounded-xl",
        isLow
          ? "bg-red-500/10 border-red-500/30"
          : "bg-bg border-border"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-bold text-secondary uppercase">
          Balance
        </p>
        <span
          className={clsx(
            "text-[10px] font-bold",
            isLow ? "text-red-400" : "text-accent"
          )}
        >
          {isLow ? "Low" : "Active"}
        </span>
      </div>
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Discovery</span>
          <span
            className={clsx(
              "font-bold",
              (credits?.discovery_credits ?? 99) < 3
                ? "text-red-400"
                : "text-primary"
            )}
          >
            {credits?.discovery_credits ?? 0}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-secondary">Enrichment</span>
          <span
            className={clsx(
              "font-bold",
              (credits?.enrichment_credits ?? 99) < 3
                ? "text-red-400"
                : "text-primary"
            )}
          >
            {credits?.enrichment_credits ?? 0}
          </span>
        </div>
      </div>
    </div>
  );
}
