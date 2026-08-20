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
  return <div className={`relative overflow-hidden border-b border-amber-300/35 bg-amber-300/[0.08] px-3 py-2 text-center ${celebrate ? "animate-pulse" : ""}`} data-testid="rival-week-patch">
    <p className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-100">Rival Week</p>
    <p className="mt-0.5 text-[10px] font-bold text-amber-50/75">Series: {series ? `${series.wins}-${series.losses}-${series.ties}` : "0-0-0"}{series?.last_meeting ? ` · ${series.last_meeting}` : ""}</p>
  </div>;
}
