import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import {
  Bell,
  Bookmark,
  Filter,
  GitCompare,
  Minus,
  Plus,
  Search,
  X,
} from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { useLeagueSettingsTab, useLeagueWorkspace } from "@/hooks/use-leagues";
import { useAddRosterEntry, useDropRosterEntry } from "@/hooks/use-roster-actions";
import {
  useToggleWatchlistPlayer,
  useUpdateWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { DEMO_LEAGUE_ID } from "@/lib/leaguePreviewData";
import { isPreDraftLeague } from "@/lib/leagueState";
import type { Player } from "@/types/player";
import type { WatchlistItem } from "@/types/watchlist";

type WatchlistRow = {
  item: WatchlistItem | null;
  player: Player;
  watchlistId: number;
};

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return "border-blue-300/45 bg-blue-400/10 text-blue-100 shadow-[0_0_22px_rgba(96,165,250,0.16)]";
    case "RB":
      return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100 shadow-[0_0_22px_rgba(52,211,153,0.16)]";
    case "WR":
      return "border-violet-300/45 bg-violet-400/10 text-violet-100 shadow-[0_0_22px_rgba(167,139,250,0.16)]";
    case "TE":
      return "border-amber-300/45 bg-amber-400/10 text-amber-100 shadow-[0_0_22px_rgba(251,191,36,0.14)]";
    case "K":
      return "border-sky-300/45 bg-sky-400/10 text-sky-100 shadow-[0_0_22px_rgba(56,189,248,0.16)]";
    default:
      return "border-slate-300/25 bg-white/5 text-slate-100";
  }
};

const projectionFor = (player: Player) =>
  Number(player.projection?.fpts ?? player.sheetProjectedSeasonPoints ?? 0);

const availabilityLabel = (item: WatchlistItem | null) => {
  const availability = item?.availability;
  if (!availability) return "Unknown";
  if (availability.status === "free_agent") return "Free Agent";
  if (availability.status === "owned") return availability.team_name ?? "Owned";
  if (availability.status === "drafted") return "Drafted";
  return availability.status.replace(/_/g, " ");
};

const tagListFor = (item: WatchlistItem | null) => item?.tags ?? [];

export default function LeagueWatchlist() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const isPreDraft = !isDemoLeague && isPreDraftLeague(settingsQuery.data);
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    !isDemoLeague && !isPreDraft && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const workspaceQuery = useLeagueWorkspace(
    parsedLeagueId,
    !isDemoLeague && !isPreDraft && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const updateWatchlistPlayer = useUpdateWatchlistPlayer();
  const ownedTeamId = workspaceQuery.data?.owned_team?.id ?? undefined;
  const addRosterEntry = useAddRosterEntry(ownedTeamId, parsedLeagueId);
  const dropRosterEntry = useDropRosterEntry(ownedTeamId, parsedLeagueId);
  const watchlists = watchlistsQuery.data?.data ?? [];
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState("ALL");
  const [tagFilter, setTagFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<"priority" | "projection" | "name">("priority");
  const [compareIds, setCompareIds] = useState<number[]>([]);

  const watchedRows = useMemo<WatchlistRow[]>(() => {
    const rowsByPlayer = new Map<number, WatchlistRow>();
    for (const list of watchlists) {
      if (list.items?.length) {
        for (const item of list.items) {
          if (!rowsByPlayer.has(item.player.id)) {
            rowsByPlayer.set(item.player.id, {
              item,
              player: item.player,
              watchlistId: list.id,
            });
          }
        }
        continue;
      }
      for (const player of list.players) {
        if (!rowsByPlayer.has(player.id)) {
          rowsByPlayer.set(player.id, { item: null, player, watchlistId: list.id });
        }
      }
    }

    return Array.from(rowsByPlayer.values()).sort((first, second) => {
      if (sortMode === "projection") {
        return projectionFor(second.player) - projectionFor(first.player);
      }
      if (sortMode === "name") {
        return first.player.name.localeCompare(second.player.name);
      }
      const priorityDelta = (first.item?.priority ?? 3) - (second.item?.priority ?? 3);
      if (priorityDelta !== 0) return priorityDelta;
      return projectionFor(second.player) - projectionFor(first.player);
    });
  }, [watchlists, sortMode]);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    for (const row of watchedRows) {
      for (const tag of tagListFor(row.item)) {
        tags.add(tag);
      }
    }
    return Array.from(tags).sort((first, second) => first.localeCompare(second));
  }, [watchedRows]);

  const filteredRows = useMemo(() => {
    const loweredQuery = query.trim().toLowerCase();
    return watchedRows
      .filter((row) => position === "ALL" || (row.player.pos ?? "").toUpperCase() === position)
      .filter((row) => tagFilter === "ALL" || tagListFor(row.item).includes(tagFilter))
      .filter((row) => {
        if (!loweredQuery) return true;
        return [row.player.name, row.player.school, row.player.pos, row.item?.notes, ...tagListFor(row.item)]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(loweredQuery));
      });
  }, [position, query, tagFilter, watchedRows]);

  const comparedRows = useMemo(
    () => watchedRows.filter((row) => compareIds.includes(row.player.id)),
    [compareIds, watchedRows]
  );

  const alertCount = watchedRows.reduce((count, row) => {
    const item = row.item;
    if (!item) return count;
    return (
      count +
      Number(item.alert_available) +
      Number(item.alert_injury) +
      Number(item.alert_projection) +
      Number(item.alert_ownership) +
      Number(item.alert_matchup)
    );
  }, 0);

  const handleQuickAdd = async (row: WatchlistRow) => {
    try {
      await addRosterEntry.mutateAsync({ player_id: row.player.id, slot: "BENCH", status: "active" });
      toast({
        title: "Player added",
        description: `${row.player.name} was added to your bench.`,
      });
    } catch (error) {
      toast({
        title: "Unable to add player",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const handleQuickDrop = async (row: WatchlistRow) => {
    const rosterEntryId = row.item?.availability?.roster_entry_id;
    if (!rosterEntryId) return;
    try {
      await dropRosterEntry.mutateAsync(rosterEntryId);
      toast({
        title: "Player dropped",
        description: `${row.player.name} was removed from your roster.`,
      });
    } catch (error) {
      toast({
        title: "Unable to drop player",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const toggleCompare = (playerId: number) => {
    setCompareIds((current) => {
      if (current.includes(playerId)) return current.filter((id) => id !== playerId);
      return [...current, playerId].slice(-3);
    });
  };

  const toggleAlert = async (
    row: WatchlistRow,
    key:
      | "alert_available"
      | "alert_injury"
      | "alert_projection"
      | "alert_ownership"
      | "alert_matchup"
  ) => {
    if (!row.item) return;
    try {
      await updateWatchlistPlayer.mutateAsync({
        watchlistId: row.watchlistId,
        playerId: row.player.id,
        payload: { [key]: !row.item[key] },
      });
    } catch (error) {
      toast({
        title: "Unable to update alert",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  if (settingsQuery.isLoading && !isDemoLeague) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <div className="rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/90 px-6 py-8 text-[10px] font-black uppercase tracking-[0.22em] text-sky-200">
          Loading league state...
        </div>
      </main>
    );
  }

  if (isPreDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/waivers`} replace />;
  }

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_8%,rgba(56,189,248,0.16),transparent_32%),radial-gradient(circle_at_72%_0%,rgba(59,130,246,0.13),transparent_38%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Watchlist
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Watchlist</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              League-specific targets with availability, alert controls, priority, tags, quick roster actions, and compare tools.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[430px]">
            <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Watched</p>
              <p className="mt-1 text-2xl font-black text-sky-100">{watchedRows.length}</p>
            </div>
            <div className="rounded-[1.25rem] border border-emerald-300/20 bg-emerald-400/10 p-4 shadow-[0_0_34px_rgba(52,211,153,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Compare</p>
              <p className="mt-1 text-2xl font-black text-emerald-100">{compareIds.length}</p>
            </div>
            <div className="rounded-[1.25rem] border border-violet-300/20 bg-violet-400/10 p-4 shadow-[0_0_34px_rgba(167,139,250,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Alerts</p>
              <p className="mt-1 text-2xl font-black text-violet-100">{alertCount}</p>
            </div>
          </div>
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {comparedRows.length > 0 ? (
        <section className="rounded-[1.75rem] border border-emerald-300/20 bg-emerald-400/[0.06] p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-emerald-200">
                Compare Watched Players
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                Select up to three targets to compare priority, availability, and projection.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => setCompareIds([])}
              className="rounded-xl border-white/10 bg-white/[0.04] text-[10px] font-black uppercase tracking-[0.16em] text-slate-300 hover:border-emerald-300/35 hover:bg-emerald-400/10 hover:text-emerald-100"
            >
              Clear
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {comparedRows.map((row) => (
              <div key={row.player.id} className="rounded-[1.25rem] border border-white/10 bg-[#08111f]/80 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-black text-slate-50">{row.player.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                      {row.player.school ?? "-"} · {row.player.pos ?? "-"}
                    </p>
                  </div>
                  <span className="rounded-xl border border-emerald-300/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-black text-emerald-100">
                    P{row.item?.priority ?? 3}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="font-black uppercase tracking-[0.16em] text-slate-500">Projection</p>
                    <p className="mt-1 text-lg font-black text-slate-100">{projectionFor(row.player).toFixed(1)}</p>
                  </div>
                  <div>
                    <p className="font-black uppercase tracking-[0.16em] text-slate-500">Status</p>
                    <p className="mt-1 text-sm font-black capitalize text-slate-200">{availabilityLabel(row.item)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(8,15,29,0.97),rgba(12,25,45,0.94))] shadow-[0_24px_80px_rgba(14,165,233,0.10)]">
        <div className="space-y-4 border-b border-sky-300/10 px-5 py-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-300">
                Saved Targets
              </h2>
              <p className="mt-2 text-xs font-semibold text-slate-500">
                Sort by priority, filter by tags, compare targets, and add/drop directly when allowed.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-[#080f1d]/80 px-3 py-2">
                <Search className="h-4 w-4 text-slate-500" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search watchlist..."
                  className="w-44 bg-transparent text-xs font-bold text-slate-200 outline-none placeholder:text-slate-600"
                />
              </div>
              <select
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as "priority" | "projection" | "name")}
                className="rounded-2xl border border-white/10 bg-[#080f1d] px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-slate-300 outline-none"
              >
                <option value="priority">Priority</option>
                <option value="projection">Projection</option>
                <option value="name">Name</option>
              </select>
              <select
                value={tagFilter}
                onChange={(event) => setTagFilter(event.target.value)}
                className="rounded-2xl border border-white/10 bg-[#080f1d] px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-slate-300 outline-none"
              >
                <option value="ALL">All Tags</option>
                {allTags.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {["ALL", "QB", "RB", "WR", "TE", "K"].map((pos) => (
              <button
                key={pos}
                type="button"
                onClick={() => setPosition(pos)}
                className={`rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] transition ${
                  position === pos
                    ? "border-sky-300/45 bg-sky-400/15 text-sky-100"
                    : "border-white/10 bg-white/[0.03] text-slate-500 hover:border-sky-300/25 hover:text-sky-100"
                }`}
              >
                {pos}
              </button>
            ))}
          </div>
        </div>

        {isDemoLeague ? (
          <div className="px-5 py-12 text-center">
            <Bookmark className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">Watchlists are saved to your account in real leagues.</p>
          </div>
        ) : watchlistsQuery.isLoading ? (
          <div className="px-5 py-12 text-center text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
            Loading watchlist...
          </div>
        ) : watchedRows.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Search className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">No watched players yet.</p>
            <p className="mt-2 text-xs font-semibold text-slate-500">Open Available Players and press Watch on any available player.</p>
          </div>
        ) : filteredRows.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Filter className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">No watched players match these filters.</p>
          </div>
        ) : (
          <div className="divide-y divide-sky-300/10">
            {filteredRows.map((row) => {
              const positionName = row.player.pos ?? "-";
              const tags = tagListFor(row.item);
              const availability = row.item?.availability;
              const canAdd = availability?.status === "free_agent" && typeof ownedTeamId === "number";
              const canDrop =
                availability?.status === "owned" &&
                availability.team_id === ownedTeamId &&
                typeof availability.roster_entry_id === "number";
              return (
                <div
                  key={row.player.id}
                  className="grid gap-4 px-5 py-5 text-sm text-slate-200 transition-all duration-200 hover:bg-sky-300/[0.045] xl:grid-cols-[minmax(0,1.3fr)_220px_230px_210px]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-base font-black text-slate-50">{row.player.name}</p>
                      <span className={`rounded-2xl border px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] ${positionTone(positionName)}`}>
                        {positionName}
                      </span>
                      <span className="rounded-2xl border border-amber-300/25 bg-amber-400/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-amber-100">
                        Priority {row.item?.priority ?? 3}
                      </span>
                    </div>
                    <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      {row.player.school ?? "-"} · {availabilityLabel(row.item)}
                    </p>
                    {row.item?.notes ? (
                      <p className="mt-3 max-w-2xl text-xs font-semibold text-slate-400">{row.item.notes}</p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {tags.length ? (
                        tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-black uppercase tracking-[0.13em] text-slate-400"
                          >
                            {tag}
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
                          No tags
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="font-black uppercase tracking-[0.16em] text-slate-500">Projection</p>
                      <p className="mt-1 text-xl font-black text-slate-100">{projectionFor(row.player).toFixed(1)}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="font-black uppercase tracking-[0.16em] text-slate-500">Status</p>
                      <p className="mt-1 text-sm font-black capitalize text-slate-200">{availabilityLabel(row.item)}</p>
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      <Bell className="h-3.5 w-3.5" />
                      Alerts
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {[
                        ["alert_available", "Avail"],
                        ["alert_injury", "Injury"],
                        ["alert_projection", "Proj"],
                        ["alert_ownership", "Own"],
                        ["alert_matchup", "Match"],
                      ].map(([key, label]) => {
                        const typedKey = key as
                          | "alert_available"
                          | "alert_injury"
                          | "alert_projection"
                          | "alert_ownership"
                          | "alert_matchup";
                        const enabled = Boolean(row.item?.[typedKey]);
                        return (
                          <button
                            key={key}
                            type="button"
                            disabled={!row.item || updateWatchlistPlayer.isPending}
                            onClick={() => void toggleAlert(row, typedKey)}
                            className={`rounded-xl border px-3 py-2 text-[9px] font-black uppercase tracking-[0.14em] transition ${
                              enabled
                                ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
                                : "border-white/10 bg-white/[0.03] text-slate-600"
                            }`}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-end gap-2 xl:justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => toggleCompare(row.player.id)}
                      className={`h-10 rounded-xl border-white/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] ${
                        compareIds.includes(row.player.id)
                          ? "bg-emerald-400/15 text-emerald-100"
                          : "bg-white/[0.04] text-slate-300 hover:border-emerald-300/35 hover:bg-emerald-400/10 hover:text-emerald-100"
                      }`}
                    >
                      <GitCompare className="mr-2 h-4 w-4" />
                      Compare
                    </Button>
                    {canDrop ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void handleQuickDrop(row)}
                        disabled={dropRosterEntry.isPending}
                        className="h-10 rounded-xl border-red-300/20 bg-red-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-red-100 hover:border-red-300/35 hover:bg-red-400/15"
                      >
                        <Minus className="mr-2 h-4 w-4" />
                        Drop
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void handleQuickAdd(row)}
                        disabled={!canAdd || addRosterEntry.isPending}
                        className="h-10 rounded-xl border-sky-300/20 bg-sky-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-sky-100 hover:border-sky-300/35 hover:bg-sky-400/15 disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="outline"
                      aria-label={`Remove ${row.player.name} from watchlist`}
                      onClick={() =>
                        void toggleWatchlistPlayer.mutateAsync({
                          watchlistId: row.watchlistId,
                          playerId: row.player.id,
                          isSaved: true,
                        })
                      }
                      className="h-10 w-10 rounded-xl border-white/10 bg-white/[0.04] p-0 text-slate-300 hover:border-red-300/35 hover:bg-red-400/10 hover:text-red-100"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
