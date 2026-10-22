import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";
import { usePlayerCard } from "@/hooks/use-players";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { PlayerRankingPortrait } from "@/components/player/PlayerRankingPortrait";
import {
  usePlayerRankings,
  rankingPeriodLabel,
  rankingPoints,
  RANKING_POSITIONS,
  type RankedPlayer,
} from "@/hooks/use-player-rankings";

export default function PlayerRankings() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const leagues = useLeagues(100, !!user);
  const mine = params.get("view") === "mine";
  const leagueId =
    Number(params.get("league")) || (mine ? leagues.data?.[0]?.id : undefined);
  const league = leagues.data?.find((l) => l.id === leagueId);
  const period = params.get("period") === "season" ? "season" : "week";
  const position = params.get("position") || "";
  const week =
    period === "week" ? Number(params.get("week")) || undefined : undefined;
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const q = usePlayerRankings(
    {
      period,
      position: position || undefined,
      week,
      league_id: leagueId,
      season: league?.season_year,
      mine,
      search: params.get("search") || undefined,
      limit: 50,
      offset,
    },
    (!mine || !!leagueId) && (!leagueId || !!league),
  );
  const [selected, setSelected] = useState<RankedPlayer | null>(null);
  const card = usePlayerCard(selected?.id, !!selected, leagueId);
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("offset");
    if (key === "period") next.delete("week");
    setParams(next);
  };
  const columns =
    position === "QB"
      ? [
          ["PASS YDS", "pass_yards"],
          ["PASS TD", "pass_tds"],
          ["INT", "interceptions"],
          ["RUSH YDS", "rush_yards"],
        ]
      : position === "K"
        ? [
            ["XP", "xp_made"],
            ["FG ≤30", "fg_made_0_30"],
            ["FG 31–40", "fg_made_31_40"],
            ["FG 41–50", "fg_made_41_50"],
            ["FG 51–60", "fg_made_51_60"],
            ["FG 61+", "fg_made_61_plus"],
          ]
        : [
            ["RUSH YDS", "rush_yards"],
            ["RUSH TD", "rush_tds"],
            ["REC", "receptions"],
            ["REC YDS", "rec_yards"],
            ["REC TD", "rec_tds"],
          ];
  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-16">
      <PageHeader
        eyebrow="Verified results"
        title="Player rankings"
        description={
          q.data
            ? `${rankingPeriodLabel(q.data)} · ${q.data.scoring_label}`
            : "Fantasy points from verified completed games."
        }
      />
      <SurfaceCard className="space-y-4">
        <div
          role="group"
          aria-label="Ranking scope"
          className="flex flex-wrap gap-2"
        >
          <Button
            variant={!mine ? "default" : "outline"}
            onClick={() => change("view", "")}
          >
            All players
          </Button>
          <Button
            variant={mine ? "default" : "outline"}
            onClick={() => change("view", "mine")}
          >
            My players by league
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="space-y-1 text-xs font-bold">
            Scoring / league
            <select
              aria-label="Rankings league"
              className="cfb-control block min-h-11 w-full px-3 text-base"
              value={leagueId || ""}
              onChange={(e) => change("league", e.target.value)}
            >
              {!mine && <option value="">Overall · standard scoring</option>}
              {leagues.data?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-bold">
            Results
            <select
              aria-label="Rankings period"
              className="cfb-control block min-h-11 w-full px-3 text-base"
              value={period}
              onChange={(e) => change("period", e.target.value)}
            >
              <option value="week">Weekly performance</option>
              <option value="season">Season totals</option>
            </select>
          </label>
          {period === "week" && (
            <label className="space-y-1 text-xs font-bold">
              Week
              <select
                aria-label="Rankings week"
                className="cfb-control block min-h-11 w-full px-3 text-base"
                value={week || ""}
                onChange={(e) => change("week", e.target.value)}
              >
                <option value="">Latest completed week</option>
                {q.data?.available_weeks.map((w) => (
                  <option key={w} value={w}>
                    Week {w}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <input
          aria-label="Search ranked players"
          className="cfb-control min-h-11 w-full px-3 text-base"
          maxLength={100}
          placeholder="Search players or schools"
          value={params.get("search") || ""}
          onChange={(e) => change("search", e.target.value)}
        />
        <div
          role="group"
          aria-label="Position filter"
          className="flex flex-wrap gap-2"
        >
          {["", ...RANKING_POSITIONS].map((p) => (
            <Button
              key={p}
              className="min-w-11 px-3 text-xs"
              variant={position === p ? "default" : "outline"}
              onClick={() => change("position", p)}
            >
              {p || "ALL"}
            </Button>
          ))}
        </div>
      </SurfaceCard>
      {mine && leagues.isError ? (
        <SurfaceCard>
          <p role="alert">Your leagues could not load.</p>
          <Button variant="outline" onClick={() => void leagues.refetch()}>
            Retry leagues
          </Button>
        </SurfaceCard>
      ) : mine && !leagues.isLoading && !leagues.data?.length ? (
        <SurfaceCard>
          Join a league to see your players’ positional ranks.
        </SurfaceCard>
      ) : q.isError ? (
        <SurfaceCard>
          <p role="alert">
            Rankings could not load. Your selected filters are preserved.
          </p>
          <Button variant="outline" onClick={() => void q.refetch()}>
            Retry rankings
          </Button>
        </SurfaceCard>
      ) : q.isLoading || (mine && leagues.isLoading) ? (
        <p role="status">Loading verified rankings…</p>
      ) : (
        q.data && (
          <>
            <p className="text-xs text-cfb-text-muted">
              {mine
                ? "Ranks compare your players against the entire eligible league pool. "
                : "Ranks are within each position. "}
              {q.data.updated_at
                ? `Verified ${new Date(q.data.updated_at).toLocaleString()}. `
                : ""}
              {q.data.pending_players > 0 &&
                `${q.data.pending_players} player results pending; missing scores are not zero.`}
            </p>
            <SurfaceCard padding="none">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">
                    Players ranked by verified fantasy points
                  </caption>
                  <thead className="bg-cfb-surface-elevated text-xs text-cfb-text-muted">
                    <tr>
                      {[
                        "POS RANK",
                        "PLAYER",
                        "FPTS",
                        "GAMES",
                        ...columns.map((c) => c[0]),
                        "STATUS",
                      ].map((h) => (
                        <th key={h} className="whitespace-nowrap px-3 py-3">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.data.map((p) => (
                      <tr
                        key={p.id}
                        className="border-t border-cfb-border-subtle"
                      >
                        <td className="px-3 py-3 font-bold">
                          {p.position} {p.position_rank ?? "—"}
                        </td>
                        <td className="px-3 py-3">
                          <button
                            className="flex min-w-[200px] items-center gap-3 text-left hover:text-cfb-brand"
                            onClick={() => setSelected(p)}
                          >
                            <PlayerRankingPortrait player={p} />
                            <span>
                              <span className="block font-bold">{p.name}</span>
                              <span className="text-xs text-cfb-text-muted">
                                {p.school}
                              </span>
                              <span className="sr-only"> Open player card</span>
                            </span>
                          </button>
                        </td>
                        <td className="px-3 py-3 font-black text-cfb-brand">
                          {rankingPoints(p.fantasy_points)}
                        </td>
                        <td className="px-3 py-3">{p.games}</td>
                        {columns.map(([label, key]) => (
                          <td key={label} className="px-3 py-3">
                            {p.fantasy_points === null
                              ? "—"
                              : (p.stats[key] ?? "—")}
                          </td>
                        ))}
                        <td className="whitespace-nowrap px-3 py-3">
                          {p.status === "final"
                            ? "Final"
                            : p.status === "bye"
                              ? "No game"
                              : p.status === "ineligible"
                                ? "Outside league pool"
                                : "Pending"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {q.data.total === 0 && (
                <p className="p-6 text-sm text-cfb-text-muted">
                  {mine
                    ? "No rostered players match these filters."
                    : "No players match these filters."}
                </p>
              )}
            </SurfaceCard>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs">{q.data.total} players</p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={offset === 0}
                  onClick={() => {
                    const n = new URLSearchParams(params);
                    n.set("offset", String(Math.max(0, offset - 50)));
                    setParams(n);
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  disabled={offset + 50 >= q.data.total}
                  onClick={() => {
                    const n = new URLSearchParams(params);
                    n.set("offset", String(offset + 50));
                    setParams(n);
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )
      )}
      {selected && (
        <PlayerCardModal
          onClose={() => setSelected(null)}
          card={card.data}
          loading={card.isLoading}
          error={card.isError}
          onRetry={() => void card.refetch()}
          player={{
            id: selected.id,
            name: selected.name,
            school: selected.school,
            position: selected.position,
            imageUrl: selected.image_url,
            rankLabel: selected.position_rank
              ? `${selected.position} ${selected.position_rank}`
              : null,
          }}
          leagueId={leagueId}
        />
      )}
    </div>
  );
}
