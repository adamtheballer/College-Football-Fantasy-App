import { Bookmark, CalendarClock, ClipboardList, Settings2, ShieldCheck, Swords } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { shouldRestrictLeagueToDraft } from "@/lib/leagueLifecycle";

const tabs = [
  { label: "Roster", mobileLabel: "Roster", path: "roster", icon: ClipboardList },
  { label: "Matchup", mobileLabel: "Matchup", path: "matchup", icon: Swords },
  { label: "Available Players", mobileLabel: "Waivers", path: "waivers", icon: ShieldCheck },
  { label: "Watchlist", mobileLabel: "Watch", path: "watchlist", icon: Bookmark },
  { label: "Settings", mobileLabel: "Settings", path: "settings", icon: Settings2 },
];

export function LeagueTabs({
  leagueId,
  draftStatus,
  leagueStatus,
}: {
  leagueId: number;
  draftStatus?: string | null;
  leagueStatus?: string | null;
}) {
  const location = useLocation();
  const hasLifecycleStatus = draftStatus !== undefined || leagueStatus !== undefined;
  const restrictedToDraft = hasLifecycleStatus && shouldRestrictLeagueToDraft({ draftStatus, leagueStatus });
  const visibleTabs = restrictedToDraft
    ? [{ label: "Draft", path: "lobby", icon: CalendarClock }]
    : tabs;

  return (
    <div
      className="w-full max-w-none gap-2 rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/85 p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_18px_44px_rgba(2,6,23,0.26)]"
      style={{ display: "grid", gridTemplateColumns: `repeat(${visibleTabs.length}, minmax(0, 1fr))` }}
    >
      {visibleTabs.map((tab) => {
        const href = `/league/${leagueId}/${tab.path}`;
        const Icon = tab.icon;
        const active =
          location.pathname === href ||
          (tab.path === "lobby" && location.pathname === `/league/${leagueId}/draft`);
        return (
          <div key={tab.path} className="min-w-0">
            <Link
              to={href}
              style={{ display: "flex", width: "100%", minWidth: 0 }}
              className={[
                "h-full min-h-[48px] flex-col items-center justify-center gap-0.5 rounded-lg border px-1.5 py-1 text-center text-[9px] font-extrabold uppercase tracking-[0.03em] transition sm:flex-row sm:gap-2 sm:rounded-xl sm:px-5 sm:py-3 sm:text-[11px] sm:tracking-[0.08em]",
                active
                  ? "border-cfb-brand/60 bg-cfb-brand/20 text-blue-50 shadow-[0_0_28px_hsl(var(--brand-primary)/0.22)]"
                  : "border-cfb-border-subtle bg-cfb-surface/70 text-cfb-text-secondary hover:border-cfb-brand/30 hover:bg-cfb-brand/[0.08] hover:text-cfb-text-primary",
              ].join(" ")}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate sm:hidden">{tab.mobileLabel}</span>
              <span className="hidden truncate sm:inline">{tab.label}</span>
            </Link>
          </div>
        );
      })}
    </div>
  );
}
