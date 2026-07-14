import { Bookmark, ClipboardList, Settings2, ShieldCheck, Swords } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const tabs = [
  { label: "Roster", path: "roster", icon: ClipboardList },
  { label: "Matchup", path: "matchup", icon: Swords },
  { label: "Available Players", path: "waivers", icon: ShieldCheck },
  { label: "Watchlist", path: "watchlist", icon: Bookmark },
  { label: "Settings", path: "settings", icon: Settings2 },
];

export function LeagueTabs({ leagueId }: { leagueId: number }) {
  const location = useLocation();

  return (
    <div
      className="w-full max-w-none gap-2 rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/85 p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_18px_44px_rgba(2,6,23,0.26)]"
      style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}
    >
      {tabs.map((tab) => {
        const href = `/league/${leagueId}/${tab.path}`;
        const Icon = tab.icon;
        const active = location.pathname === href;
        return (
          <div key={tab.path} className="min-w-0">
            <Link
              to={href}
              style={{ display: "flex", width: "100%", minWidth: 0 }}
              className={[
                "h-full items-center justify-center gap-2 rounded-xl border px-3 py-3 text-center text-[11px] font-extrabold uppercase tracking-[0.08em] transition sm:px-5",
                active
                  ? "border-cfb-brand/60 bg-cfb-brand/20 text-blue-50 shadow-[0_0_28px_hsl(var(--brand-primary)/0.22)]"
                  : "border-cfb-border-subtle bg-cfb-surface/70 text-cfb-text-secondary hover:border-cfb-brand/30 hover:bg-cfb-brand/[0.08] hover:text-cfb-text-primary",
              ].join(" ")}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{tab.label}</span>
            </Link>
          </div>
        );
      })}
    </div>
  );
}
