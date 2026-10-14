import { useSearchParams } from "react-router-dom";
import React, { useEffect, useMemo, useState } from "react";
import { Search, ShieldAlert, AlertTriangle, TimerReset } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { useInjuryUpdates } from "@/hooks/use-injury-updates";
import { Button } from "@/components/ui/button";
import { PlayerAvailabilityIndicator } from "@/lib/playerAvailability";
import { usePlayerCard } from "@/hooks/use-players";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type InjuryItem = {
  id: number;
  name: string;
  team: string;
  conference: string;
  pos: string;
  status: string;
  injury: string;
  returnTimeline: string;
  projectionDelta: number | null;
  lastUpdated: string;
  sourceUrl?: string | null;
};

const statusStyles: Record<string, string> = {
  TBD: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  OUT_FOR_SEASON: "bg-red-600/20 text-red-300 border-red-500/40",
  OUT: "bg-red-500/15 text-red-400 border-red-500/30",
  DAY_TO_DAY: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  SUSPENDED: "bg-red-500/15 text-red-400 border-red-500/30",
  INACTIVE: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  IR: "bg-red-600/20 text-red-300 border-red-500/40",
  N_A: "bg-slate-500/10 text-slate-300 border-slate-500/30",
  DOUBTFUL: "bg-red-500/15 text-red-300 border-red-500/30",
  QUESTIONABLE: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  PROBABLE: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  FULL: "bg-slate-500/10 text-slate-300 border-slate-500/30",
};

const conferenceSortOrder: Record<string, number> = {
  SEC: 0,
  BIG10: 1,
  BIG12: 2,
  ACC: 3,
};

const positionSortOrder: Record<string, number> = {
  QB: 0,
  RB: 1,
  WR: 2,
  TE: 3,
  K: 4,
};

const statusSortOrder: Record<string, number> = {
  OUT_FOR_SEASON: 0,
  OUT: 1,
  DOUBTFUL: 2,
  QUESTIONABLE: 3,
  DAY_TO_DAY: 4,
  PROBABLE: 5,
  TBD: 6,
  INACTIVE: 7,
  IR: 8,
  SUSPENDED: 9,
  FULL: 10,
  N_A: 11,
};

const statusLabel = (value: string) => (value === "N_A" ? "N/A" : value.split("_").join(" "));

export const buildInjuryPlayerCard = (injury: InjuryItem) => ({
  id: injury.id,
  name: injury.name,
  school: injury.team,
  position: injury.pos,
  status: statusLabel(injury.status),
});

export default function InjuryCenter() {
  const [searchQuery, setSearchQuery] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("ALL");
  const [searchParams] = useSearchParams();
  const playerParam = Number(searchParams.get("playerId"));
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(Number.isSafeInteger(playerParam) && playerParam > 0 ? playerParam : null);
  useEffect(() => { setSelectedPlayerId(Number.isSafeInteger(playerParam) && playerParam > 0 ? playerParam : null); }, [playerParam]);
  const leagueParam = Number(searchParams.get("leagueId"));
  const leagueId = Number.isSafeInteger(leagueParam) && leagueParam > 0 ? leagueParam : undefined;
  const injuryQuery = useInjuryUpdates();
  const injuries: InjuryItem[] = useMemo(() => (injuryQuery.data?.data ?? []).map((row) => ({
    id: row.player_id, name: row.player_name, team: row.team,
    conference: row.conference || "UNKNOWN", pos: row.position, status: row.status,
    injury: [row.injury, row.notes].filter(Boolean).join(" • ") || "Availability designation; no injury detail reported",
    returnTimeline: row.return_timeline || "Return not confirmed",
    projectionDelta: row.projection_delta,
    lastUpdated: row.last_updated ? new Date(row.last_updated).toLocaleString() : "Report time unavailable",
    sourceUrl: row.source_url,
  })), [injuryQuery.data]);
  const playerCardQuery = usePlayerCard(selectedPlayerId, selectedPlayerId !== null, leagueId);

  const filtered = useMemo(() => {
    return injuries
      .filter((row) => conferenceFilter === "ALL" || row.conference === conferenceFilter.replace(" ", ""))
      .filter((row) =>
        row.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        row.team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        row.pos.toLowerCase().includes(searchQuery.toLowerCase())
      )
      .sort((a, b) => {
        if (a.conference !== b.conference) {
          const confRankA = conferenceSortOrder[a.conference] ?? 99;
          const confRankB = conferenceSortOrder[b.conference] ?? 99;
          if (confRankA !== confRankB) {
            return confRankA - confRankB;
          }
          return a.conference.localeCompare(b.conference);
        }
        if (a.pos !== b.pos) {
          const posRankA = positionSortOrder[a.pos] ?? 99;
          const posRankB = positionSortOrder[b.pos] ?? 99;
          if (posRankA !== posRankB) {
            return posRankA - posRankB;
          }
          return a.pos.localeCompare(b.pos);
        }
        if (a.status !== b.status) {
          const statusRankA = statusSortOrder[a.status] ?? 99;
          const statusRankB = statusSortOrder[b.status] ?? 99;
          if (statusRankA !== statusRankB) {
            return statusRankA - statusRankB;
          }
          return a.status.localeCompare(b.status);
        }
        return a.name.localeCompare(b.name);
      });
  }, [injuries, searchQuery, conferenceFilter]);

  const openPlayer = (playerId: number) => {
    setSelectedPlayerId(playerId);
  };
  const selectedInjury = injuries.find((injury) => injury.id === selectedPlayerId) ?? null;

  return (
    <div className="max-w-6xl mx-auto space-y-10 animate-in fade-in duration-1000">
      {selectedPlayerId && (selectedInjury || playerCardQuery.data) ? (
        <PlayerCardModal
          player={selectedInjury ? buildInjuryPlayerCard(selectedInjury) : playerCardQuery.data!.player}
          leagueId={leagueId}
          card={playerCardQuery.data}
          error={playerCardQuery.isError}
          loading={playerCardQuery.isLoading}
          title="Injury Player Card"
          onClose={() => setSelectedPlayerId(null)}
          onRetry={() => void playerCardQuery.refetch()}
        />
      ) : null}

      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">
            Injury Center
          </h1>
          <p className="text-[11px] font-black tracking-[0.4em] text-primary uppercase">
            Fantasy-Relevant Injury Tracker
          </p>
        </div>
        <div className="w-full md:w-auto flex flex-col md:flex-row gap-3">
          <Select value={conferenceFilter} onValueChange={setConferenceFilter}>
            <SelectTrigger className="w-full md:w-[180px] bg-white/5 border-white/10 rounded-[1.5rem] h-14 text-xs font-bold uppercase tracking-widest">
              <SelectValue placeholder="Conference" />
            </SelectTrigger>
            <SelectContent className="bg-[#0A0C10] border-border rounded-2xl">
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="SEC">SEC</SelectItem>
              <SelectItem value="ACC">ACC</SelectItem>
              <SelectItem value="BIG 10">Big 10</SelectItem>
              <SelectItem value="BIG 12">Big 12</SelectItem>
            </SelectContent>
          </Select>
          <div className="relative w-full md:w-[420px]">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              placeholder="Search player, team, or position..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-14 bg-white/5 border-white/10 rounded-[1.5rem] h-14 text-xs font-bold uppercase tracking-widest"
            />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cfb-border-subtle bg-cfb-surface p-4">
        <div className="space-y-1 text-sm text-cfb-text-secondary">
          <p className="font-semibold text-cfb-text-primary">{injuryQuery.data ? `${injuryQuery.data.season} • Fantasy Week ${injuryQuery.data.week}` : "Current fantasy week"}</p>
          <p>O = Out · D = Doubtful · Q = Questionable · P = Probable</p>
          <p>Missing reports do not confirm a player is healthy. Check the report time before setting your lineup.</p>
        </div>
        <Button variant="outline" disabled={injuryQuery.isFetching} onClick={() => void injuryQuery.refetch()}>{injuryQuery.isFetching ? "Checking…" : "Refresh updates"}</Button>
      </div>
      {injuryQuery.isError ? <div role="alert" className="rounded-lg border border-red-400/40 bg-red-400/10 p-4 text-sm text-red-200">Injury updates could not be refreshed. {injuryQuery.data ? "Showing the last loaded reports." : "No current reports could be loaded."} Use Refresh updates to retry.</div> : null}

      <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl">
        <CardHeader className="px-10 py-8 border-b border-white/5 bg-white/5">
          <div className="flex items-center justify-between">
            <CardTitle className="text-[10px] font-black tracking-[0.5em] text-primary uppercase">
              Injury Report
            </CardTitle>
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-4 h-4 text-primary" />
              <span className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">
                Sourced Reports
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-white/10">
            {filtered.map((row) => (
              <div
                key={row.id}
                className="grid grid-cols-1 md:grid-cols-[1.3fr_0.6fr_0.9fr_0.9fr_0.6fr] gap-4 items-center px-4 py-5 sm:px-6 hover:bg-white/[0.04] transition-all"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-3">
                    <button type="button" onClick={() => openPlayer(row.id)} className="text-left text-sm font-bold text-cfb-text-primary hover:text-cfb-brand"><PlayerAvailabilityIndicator status={row.status}>{row.name}</PlayerAvailabilityIndicator></button>
                    <span className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">
                      {row.team} • {row.conference} • {row.pos}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">
                    <AlertTriangle className="w-3 h-3" />
                    {row.injury}
                  </div>
                </div>

                <div>
                  <span
                    className={cn(
                      "px-4 py-1.5 rounded-xl border text-[9px] font-black uppercase tracking-widest",
                      statusStyles[row.status] ?? statusStyles.TBD
                    )}
                  >
                    {statusLabel(row.status)}
                  </span>
                </div>

                <div className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground/70">
                  {row.returnTimeline}
                </div>

                <div className="text-[12px] font-black text-foreground">
                  {row.projectionDelta === null ? "Impact not reported" : `${row.projectionDelta > 0 ? "+" : ""}${row.projectionDelta.toFixed(1)} pts`}
                </div>

                <div className="text-xs text-cfb-text-secondary space-y-2">
                  <span className="flex items-center gap-2">
                  <TimerReset className="w-3 h-3" />
                  {row.lastUpdated}
                  </span>
                  {row.sourceUrl ? <a href={row.sourceUrl} target="_blank" rel="noopener noreferrer" className="font-semibold text-cfb-brand underline">View source</a> : null}
                </div>
              </div>
            ))}
            {injuryQuery.isLoading ? <p role="status" className="p-6 text-sm text-cfb-text-secondary">Loading current injury reports…</p> : null}
            {!injuryQuery.isLoading && !injuryQuery.isError && filtered.length === 0 && (
              <div className="px-10 py-10 text-center">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                  No current Power 4 injury reports are available for this filter. Reports may still be pending.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
