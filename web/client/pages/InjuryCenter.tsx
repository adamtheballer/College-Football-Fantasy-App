import React, { useMemo, useState, useEffect } from "react";
import { Search, ShieldAlert, AlertTriangle, TimerReset } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { apiGet } from "@/lib/api";
import { usePlayerDetail } from "@/hooks/use-players";
import type { Player } from "@/types/player";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type InjuryItem = {
  id: number;
  name: string;
  team: string;
  conference: string;
  pos: string;
  status: string;
  injury: string;
  returnTimeline: string;
  projectionDelta: number;
  lastUpdated: string;
};

const statusStyles: Record<string, string> = {
  OUT_FOR_SEASON: "bg-red-600/20 text-red-300 border-red-500/40",
  OUT: "bg-red-500/15 text-red-400 border-red-500/30",
  DOUBTFUL: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  QUESTIONABLE: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  PROBABLE: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
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
  PROBABLE: 4,
  FULL: 5,
};

const statusLabel = (value: string) => value.split("_").join(" ");

export default function InjuryCenter() {
  const [searchQuery, setSearchQuery] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("ALL");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const [injuries, setInjuries] = useState<InjuryItem[]>([]);
  const { data: playerDetail } = usePlayerDetail(selectedPlayerId, selectedPlayerId !== null);

  useEffect(() => {
    const controller = new AbortController();
    const season = new Date().getFullYear();
    const week = 1;
    const conferenceParam =
      conferenceFilter === "ALL"
        ? undefined
        : conferenceFilter.replace(" ", "");
    apiGet<{ data: any[] }>(
      "/injuries",
      { season, week, conference: conferenceParam },
      controller.signal
    )
      .then((payload) => {
        const mapped = payload.data.map((row) => ({
          id: row.player_id,
          name: row.player_name,
          team: row.team,
          conference: row.conference || "UNKNOWN",
          pos: row.position,
          status: row.status,
          injury: row.injury || "Injury designation",
          returnTimeline: row.return_timeline || "TBD",
          projectionDelta: row.projection_delta ?? 0,
          lastUpdated: row.last_updated
            ? new Date(row.last_updated).toLocaleString()
            : "Updated recently",
        }));
        setInjuries(mapped);
      })
      .catch(() => {
        setInjuries([]);
      });
    return () => controller.abort();
  }, [conferenceFilter]);

  useEffect(() => {
    if (!playerDetail) return;
    setSelectedPlayer(playerDetail);
    setIsPlayerModalOpen(true);
  }, [playerDetail]);

  const filtered = useMemo(() => {
    return injuries
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
  }, [injuries, searchQuery]);

  const openPlayer = (playerId: number) => {
    setSelectedPlayer(null);
    setSelectedPlayerId(playerId);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-10 animate-in fade-in duration-1000">
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />

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

      <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl">
        <CardHeader className="px-10 py-8 border-b border-white/5 bg-white/5">
          <div className="flex items-center justify-between">
            <CardTitle className="text-[10px] font-black tracking-[0.5em] text-primary uppercase">
              Injury Report
            </CardTitle>
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-4 h-4 text-primary" />
              <span className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">
                Live Updates
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-white/10">
            {filtered.map((row) => (
              <div
                key={row.id}
                onClick={() => openPlayer(row.id)}
                className="grid grid-cols-1 md:grid-cols-[1.3fr_0.6fr_0.9fr_0.9fr_0.6fr] gap-6 items-center px-10 py-6 hover:bg-white/[0.04] transition-all cursor-pointer"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <h3 className="text-[14px] font-black italic uppercase text-foreground">{row.name}</h3>
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
                      statusStyles[row.status]
                    )}
                  >
                    {statusLabel(row.status)}
                  </span>
                </div>

                <div className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground/70">
                  {row.returnTimeline}
                </div>

                <div className="text-[12px] font-black text-foreground">
                  {row.projectionDelta > 0 ? "+" : ""}
                  {row.projectionDelta.toFixed(1)} pts
                </div>

                <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/40 flex items-center gap-2">
                  <TimerReset className="w-3 h-3" />
                  {row.lastUpdated}
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="px-10 py-10 text-center">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                  No Power 4 injury updates found for this filter.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
