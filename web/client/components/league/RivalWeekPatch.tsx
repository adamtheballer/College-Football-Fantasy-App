import { useEffect, useState } from "react";

import type { RivalryMatchup } from "@/types/league";

export function RivalWeekPatch({ rivalry, leagueId, matchupId }: { rivalry?: RivalryMatchup | null; leagueId: number; matchupId: number | null | undefined }) {
  const [celebrate, setCelebrate] = useState(false);
  useEffect(() => {
    if (!rivalry?.is_rivalry_matchup || !matchupId || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const key = `cff-rival-week:${leagueId}:${matchupId}`;
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, "1"); setCelebrate(true);
    const timer = window.setTimeout(() => setCelebrate(false), 900);
    return () => window.clearTimeout(timer);
  }, [leagueId, matchupId, rivalry?.is_rivalry_matchup]);
  if (!rivalry?.is_rivalry_matchup) return null;
  const series = rivalry.series;
  return (
    <div
      className={`relative flex items-center justify-center gap-2.5 overflow-hidden border-b border-amber-300/35 bg-amber-300/[0.08] px-3 py-2 text-center ${celebrate ? "animate-pulse" : ""}`}
      data-testid="rival-week-patch"
    >
      <span
        aria-label="Rivalry Bowl patch"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-amber-200/70 bg-slate-950 shadow-sm"
        data-testid="rival-bowl-emblem"
        role="img"
      >
        {/* Original bowl-game mark: a football field, bowl silhouette, and laurels.
            It deliberately does not reproduce any real bowl game's protected logo. */}
        <svg aria-hidden="true" className="h-7 w-7" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="20" fill="#10233A" stroke="#F7D66A" strokeWidth="2" />
          <path d="M16 17.5h16M24 13v9" stroke="#74C7FF" strokeLinecap="round" strokeWidth="1.5" />
          <path d="M14.5 22.5h19c-.8 7.2-4.1 10.8-9.5 10.8s-8.7-3.6-9.5-10.8Z" fill="#B6425B" stroke="#FFF1BE" strokeWidth="1.5" />
          <path d="M20 36.5h8M24 33v3.5" stroke="#FFF1BE" strokeLinecap="round" strokeWidth="1.5" />
          <path d="M12.2 27.7c-2.3-1.8-3.4-4.5-3.1-7.4M35.8 27.7c2.3-1.8 3.4-4.5 3.1-7.4" stroke="#F7D66A" strokeLinecap="round" strokeWidth="1.5" />
        </svg>
      </span>
      <div className="min-w-0 text-left">
        <p className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-100">Rivalry Bowl</p>
        <p className="mt-0.5 text-[10px] font-bold text-amber-50/75">
          Rival week · Series: {series ? `${series.wins}-${series.losses}-${series.ties}` : "0-0-0"}
          {series?.last_meeting ? ` · ${series.last_meeting}` : ""}
        </p>
      </div>
    </div>
  );
}
