import { useMemo, useState } from "react";
import {
  ArrowRightLeft,
  BarChart3,
  ChevronRight,
  Search,
  SlidersHorizontal,
  Star,
  Trophy,
  UserRoundSearch,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";
import { useDraftPlayerPool, usePlayerCard } from "@/hooks/use-players";
import { buildPlayerCompareRows, toProjectedPoints } from "@/lib/playerCompareValue";
import { cn } from "@/lib/utils";

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
type PositionFilter = (typeof POSITIONS)[number];
type SortMode = "overall" | "cfb27" | "rank" | "name";

const positionStyle: Record<string, string> = {
  QB: "border-blue-300/35 bg-blue-400/12 text-blue-100",
  RB: "border-emerald-300/35 bg-emerald-400/12 text-emerald-100",
  WR: "border-fuchsia-300/35 bg-fuchsia-400/12 text-fuchsia-100",
  TE: "border-amber-300/35 bg-amber-400/12 text-amber-100",
  K: "border-sky-300/35 bg-sky-400/12 text-sky-100",
};

const compareTools = [
  { Icon: Trophy, label: "Rank players by CFB27 baseline OVR" },
  { Icon: UserRoundSearch, label: "Open full player cards" },
  { Icon: BarChart3, label: "Blend weekly performance as season data arrives" },
  { Icon: Star, label: "Find position-relative trade targets" },
] as const;

const formatOverall = (value: number | null) => (typeof value === "number" ? String(value) : "N/A");

const valueTone = (overall: number | null) => {
  if (overall === null) return "border-white/10 bg-white/[0.035] text-slate-300";
  if (overall >= 90) return "border-cfb-gold/50 bg-cfb-gold/15 text-yellow-100";
  if (overall >= 80) return "border-cfb-brand/50 bg-cfb-brand/15 text-blue-100";
  if (overall >= 70) return "border-cfb-cyan/45 bg-cfb-cyan/12 text-cyan-100";
  return "border-white/12 bg-white/[0.045] text-slate-100";
};

export default function PlayerCompare() {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const { data: leagues = [] } = useLeagues(50, isLoggedIn);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState<PositionFilter>("ALL");
  const [sortMode, setSortMode] = useState<SortMode>("overall");
  const [selectedLeagueId, setSelectedLeagueId] = useState<string>("");
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);

  const {
    data: playersPayload,
    isLoading,
    isError,
    error,
  } = useDraftPlayerPool({
    limit: 200,
    sort: "rank",
    fetchAll: true,
    maxPages: 50,
  });

  const { data: playerCard, isLoading: playerCardLoading } = usePlayerCard(
    selectedPlayerId,
    Boolean(selectedPlayerId)
  );

  const compareRows = useMemo(
    () => buildPlayerCompareRows(playersPayload?.data ?? []),
    [playersPayload?.data]
  );

  const selectedPlayer = useMemo(
    () => compareRows.find((player) => player.id === selectedPlayerId) ?? null,
    [compareRows, selectedPlayerId]
  );

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    const rows = compareRows
      .filter((player) => position === "ALL" || player.pos === position)
      .filter((player) =>
        query
          ? [player.name, player.school, player.pos, player.conf].some((value) =>
              value.toLowerCase().includes(query)
            )
          : true
      );

    return [...rows].sort((left, right) => {
      if (sortMode === "cfb27") return (right.cfb27Overall ?? -1) - (left.cfb27Overall ?? -1);
      if (sortMode === "rank") return (left.boardRank ?? left.rank ?? 999) - (right.boardRank ?? right.rank ?? 999);
      if (sortMode === "name") return left.name.localeCompare(right.name);
      return (right.valueOverall ?? -1) - (left.valueOverall ?? -1) || left.compareRank - right.compareRank;
    });
  }, [compareRows, position, search, sortMode]);

  const selectedLeague = leagues.find((league) => String(league.id) === selectedLeagueId) ?? null;
  const topOverall = compareRows[0]?.valueOverall ?? null;
  const playerCount = compareRows.length;

  const openTradeBuilder = (playerId: number) => {
    if (!isLoggedIn) {
      navigate("/login");
      return;
    }
    if (!selectedLeagueId) {
      return;
    }
    navigate(`/trade/${selectedLeagueId}/${playerId}`);
  };

  return (
    <div className="relative z-10 mx-auto max-w-7xl space-y-8 pb-20 animate-in fade-in duration-700">
      <section className="relative overflow-hidden rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/80 p-6 shadow-[0_20px_70px_rgba(2,6,23,0.28)] backdrop-blur-xl sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cfb-brand/20 blur-[90px]" />
        <div className="pointer-events-none absolute -bottom-20 left-12 h-48 w-48 rounded-full bg-cfb-pink/12 blur-[80px]" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_360px] lg:items-end">
          <div>
            <p className="cfb-micro-label text-cfb-brand">Player Value Lab</p>
            <h1 className="mt-4 cfb-display-title text-5xl sm:text-6xl">
              Player Compare
            </h1>
            <p className="mt-4 max-w-3xl text-base font-semibold leading-7 text-cfb-text-secondary">
              Compare every player by a 99-point OVR board. Week 1 starts from matched CFB27 ratings; as real results arrive, the model shifts toward weekly production, position-relative performance, and performance against projection.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-cfb-brand/35 bg-cfb-brand/12 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cfb-text-muted">Players</p>
              <p className="mt-2 text-4xl font-black tabular-nums text-white">{playerCount}</p>
            </div>
            <div className="rounded-2xl border border-cfb-gold/35 bg-cfb-gold/12 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cfb-text-muted">Top OVR</p>
              <p className="mt-2 text-4xl font-black tabular-nums text-white">{formatOverall(topOverall)}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/70 p-4 backdrop-blur-xl lg:grid-cols-[1fr_auto_auto] lg:items-center">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search players, schools, positions..."
            className="h-12 rounded-2xl border-cfb-border-subtle bg-white/[0.04] pl-11 text-sm font-bold"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {POSITIONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setPosition(item)}
              className={cn(
                "rounded-2xl border px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] transition",
                position === item
                  ? "border-cfb-brand bg-cfb-brand text-slate-950"
                  : "border-white/10 bg-white/[0.04] text-cfb-text-secondary hover:border-cfb-brand/50 hover:text-white"
              )}
            >
              {item}
            </button>
          ))}
        </div>
        <Select value={sortMode} onValueChange={(value) => setSortMode(value as SortMode)}>
          <SelectTrigger className="h-12 rounded-2xl border-cfb-border-subtle bg-white/[0.04] text-[10px] font-black uppercase tracking-[0.16em] lg:w-52">
            <SlidersHorizontal className="mr-2 h-4 w-4" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="overall">Sort: Overall</SelectItem>
            <SelectItem value="cfb27">Sort: CFB27</SelectItem>
            <SelectItem value="rank">Sort: Board Rank</SelectItem>
            <SelectItem value="name">Sort: Name</SelectItem>
          </SelectContent>
        </Select>
      </section>

      <section className="grid gap-5 lg:grid-cols-[1fr_330px]">
        <div className="overflow-hidden rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/70 backdrop-blur-xl">
          <div className="grid grid-cols-[64px_1fr_88px_92px_120px] gap-4 border-b border-white/10 px-5 py-4 text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted max-lg:hidden">
            <span>RK</span>
            <span>Player</span>
            <span>Pos</span>
            <span>OVR</span>
            <span className="text-right">CFB27</span>
          </div>

          {isLoading ? (
            <div className="p-10 text-center text-[10px] font-black uppercase tracking-[0.24em] text-cfb-text-muted">
              Loading player value board...
            </div>
          ) : isError ? (
            <div className="p-10 text-center text-[10px] font-black uppercase tracking-[0.24em] text-red-200">
              Unable to load players{error instanceof Error ? `: ${error.message}` : "."}
            </div>
          ) : filteredRows.length === 0 ? (
            <div className="p-10 text-center text-[10px] font-black uppercase tracking-[0.24em] text-cfb-text-muted">
              No players match the current compare filters.
            </div>
          ) : (
            <div className="divide-y divide-white/10">
              {filteredRows.map((player) => (
                <button
                  key={player.id}
                  type="button"
                  onClick={() => setSelectedPlayerId(player.id)}
                  className="grid w-full grid-cols-[52px_1fr_auto] gap-4 px-5 py-4 text-left transition hover:bg-white/[0.045] lg:grid-cols-[64px_1fr_88px_92px_120px] lg:items-center"
                >
                  <span className="text-2xl font-black italic tabular-nums text-white/80">
                    {player.compareRank}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-base font-black text-white">{player.name}</span>
                    <span className="mt-1 block truncate text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
                      {player.school} • Board {player.boardRank ?? player.rank ?? "N/A"}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "rounded-xl border px-3 py-2 text-center text-[10px] font-black uppercase tracking-[0.16em]",
                      positionStyle[player.pos] ?? "border-white/10 bg-white/[0.04] text-white"
                    )}
                  >
                    {player.pos}
                  </span>
                  <span
                    className={cn(
                      "hidden rounded-2xl border px-3 py-2 text-center text-xl font-black tabular-nums lg:block",
                      valueTone(player.valueOverall)
                    )}
                  >
                    {formatOverall(player.valueOverall)}
                  </span>
                  <span className="hidden text-right lg:block">
                    <span className="block text-lg font-black tabular-nums text-cfb-cyan">
                      {formatOverall(player.cfb27Overall)}
                    </span>
                    <span className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">
                      Base
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="space-y-5">
          <div className="rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/70 p-5 backdrop-blur-xl">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cfb-brand/30 bg-cfb-brand/15 text-cfb-brand">
                <ArrowRightLeft className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-black text-white">Trade from Compare</p>
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
                  Select league first
                </p>
              </div>
            </div>
            <Select value={selectedLeagueId} onValueChange={setSelectedLeagueId} disabled={!isLoggedIn || !leagues.length}>
              <SelectTrigger className="mt-5 h-12 rounded-2xl border-cfb-border-subtle bg-white/[0.04] text-[10px] font-black uppercase tracking-[0.16em]">
                <SelectValue placeholder={isLoggedIn ? "Choose league" : "Sign in required"} />
              </SelectTrigger>
              <SelectContent>
                {leagues.map((league) => (
                  <SelectItem key={league.id} value={String(league.id)}>
                    {league.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-4 text-xs font-semibold leading-5 text-cfb-text-secondary">
              Open any player card, then use Trade Player to jump into that league’s trade builder.
              {selectedLeague ? ` Selected: ${selectedLeague.name}.` : ""}
            </p>
          </div>

          <div className="rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/70 p-5 backdrop-blur-xl">
            <p className="cfb-micro-label text-cfb-gold">How OVR works</p>
            <div className="mt-4 space-y-3 text-sm font-semibold leading-6 text-cfb-text-secondary">
              <p>
                Week 1 OVR is anchored to the matched CFB27 player rating. If a player cannot be matched to a CFB27 rating, the app shows N/A instead of inventing a fake rating.
              </p>
              <p>
                During the season, actual weekly fantasy output, same-position peer performance, and performance against projection gradually carry more weight.
              </p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface/70 p-5 backdrop-blur-xl">
            <p className="cfb-micro-label text-cfb-pink">Compare tools</p>
            <div className="mt-4 grid gap-3">
              {compareTools.map(({ Icon, label }) => (
                <div key={label} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3">
                  <Icon className="h-4 w-4 text-cfb-brand" />
                  <span className="text-xs font-black uppercase tracking-[0.14em] text-cfb-text-secondary">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>

      {selectedPlayer ? (
        <PlayerCardModal
          card={playerCard}
          loading={playerCardLoading}
          onClose={() => setSelectedPlayerId(null)}
          player={{
            id: selectedPlayer.id,
            name: selectedPlayer.name,
            school: selectedPlayer.school,
            position: selectedPlayer.pos,
            rankLabel: `Compare Rank #${selectedPlayer.compareRank} • OVR ${formatOverall(selectedPlayer.valueOverall)} • CFB27 ${formatOverall(selectedPlayer.cfb27Overall)}`,
            projectedPoints: toProjectedPoints(selectedPlayer),
            playerClass: selectedPlayer.playerClass,
            status: selectedPlayer.status,
            projection: selectedPlayer.projection,
            sheetProjectionStats: selectedPlayer.sheetProjectionStats,
          }}
          title="Compare Card"
          note={
            selectedLeague
              ? `Trade action will open ${selectedLeague.name}'s trade builder for this player.`
              : "Select a league on Player Compare before using the Trade Player action."
          }
          action={{
            label: selectedLeague ? "Trade Player" : isLoggedIn ? "Select League First" : "Sign In To Trade",
            onClick: () => openTradeBuilder(selectedPlayer.id),
          }}
        />
      ) : null}
    </div>
  );
}
