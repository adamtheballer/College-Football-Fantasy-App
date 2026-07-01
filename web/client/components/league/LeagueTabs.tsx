import { ClipboardList, Settings2, ShieldCheck, Swords } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const tabs = [
  { label: "Roster", path: "roster", icon: ClipboardList },
  { label: "Matchup", path: "matchup", icon: Swords },
  { label: "Waiver Wire", path: "waivers", icon: ShieldCheck },
  { label: "Settings", path: "settings", icon: Settings2 },
];

export function LeagueTabs({ leagueId }: { leagueId: number }) {
  const location = useLocation();

  return (
    <div
      className="w-full max-w-none gap-2 rounded-[1.25rem] border border-sky-300/15 bg-[linear-gradient(135deg,rgba(7,20,38,0.92),rgba(12,29,54,0.78))] p-2 shadow-[inset_0_1px_0_rgba(125,211,252,0.10),0_18px_50px_rgba(14,165,233,0.08)]"
      style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}
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
                  ? "border-sky-300/55 bg-sky-300/20 text-sky-50 shadow-[0_0_28px_rgba(56,189,248,0.24)]"
                  : "border-white/10 bg-white/5 text-slate-400 hover:border-sky-300/20 hover:bg-sky-300/[0.06] hover:text-slate-50",
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
