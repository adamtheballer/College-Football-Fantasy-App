import { Trophy } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { EmptyState, ErrorState, SkeletonState } from "@/components/states";
import { useLeagueDetail, useLeaguePostseasonBracket } from "@/hooks/use-leagues";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { PostseasonMatchup, PostseasonTeam } from "@/types/league";

const placementLabel: Record<string, string> = {
  QUARTERFINAL: "Quarterfinal",
  SEMIFINAL: "Semifinal",
  CHAMPIONSHIP: "Championship",
  PLACEMENT_SEMIFINAL: "Placement semifinal",
  THIRD_PLACE: "Third place",
  FIFTH_PLACE: "Fifth place",
  SEVENTH_PLACE: "Seventh place",
};

function TeamLine({ team, seed, score, winner }: { team?: PostseasonTeam | null; seed?: number | null; score?: number | null; winner?: boolean }) {
  return (
    <div className={`flex min-w-0 items-center gap-2 rounded-lg px-2 py-2 ${winner ? "bg-cfb-brand/10" : "bg-cfb-surface-raised/60"}`}>
      <span className="w-5 text-[10px] font-black tabular-nums text-cfb-text-muted">{seed ? `#${seed}` : "—"}</span>
      <ManagerAvatar avatarUrl={team?.manager_avatar_url} managerName={team?.manager_name ?? team?.team_name} size="xs" />
      <span className="min-w-0 flex-1 truncate text-xs font-bold text-cfb-text-primary">{team?.team_name ?? "TBD"}</span>
      <span className="text-xs font-black tabular-nums text-cfb-text-primary">{typeof score === "number" ? score.toFixed(1) : "—"}</span>
    </div>
  );
}

function MatchupCard({ leagueId, matchup }: { leagueId: number; matchup: PostseasonMatchup }) {
  const title = placementLabel[matchup.matchup_type] ?? matchup.matchup_type.replace(/_/g, " ");
  const content = (
    <article className={`rounded-xl border p-3 ${matchup.matchup_type === "CHAMPIONSHIP" ? "border-amber-300/45 bg-amber-300/[0.06]" : "border-cfb-border-subtle bg-cfb-surface"}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[10px] font-black uppercase tracking-[0.15em] text-cfb-brand">{title}</span>
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-cfb-text-muted">Week {matchup.week} · {matchup.status}</span>
      </div>
      <div className="space-y-1">
        <TeamLine team={matchup.team_a} seed={matchup.team_a_seed} score={matchup.team_a_score} winner={matchup.winner_team_id === matchup.team_a?.team_id} />
        <TeamLine team={matchup.team_b} seed={matchup.team_b_seed} score={matchup.team_b_score} winner={matchup.winner_team_id === matchup.team_b?.team_id} />
      </div>
      {matchup.tiebreaker_used ? <p className="mt-2 text-[10px] font-medium text-cfb-text-muted">Tie resolved by higher original seed.</p> : null}
    </article>
  );
  return matchup.fantasy_matchup_id ? <Link to={`/league/${leagueId}/matchup?week=${matchup.week}&matchup=${matchup.fantasy_matchup_id}`}>{content}</Link> : content;
}

export default function LeaguePlayoffs() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({ draftStatus: leagueQuery.data?.draft?.status, leagueStatus: leagueQuery.data?.status });
  const postseasonQuery = useLeaguePostseasonBracket(parsedLeagueId, postDraft);
  const data = postseasonQuery.data;

  if (leagueQuery.isLoading || postseasonQuery.isLoading) return <main className="mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8"><SkeletonState rows={7} label="Loading playoffs" /></main>;
  if (leagueQuery.isError || postseasonQuery.isError) return <main className="mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8"><ErrorState title="Unable to load playoffs" message="The playoff picture could not be loaded." retryLabel="Try again" onRetry={() => void postseasonQuery.refetch()} /></main>;
  if (!leagueQuery.data || !data || !postDraft) return <main className="mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8"><EmptyState title="Playoff picture unavailable" description="Playoff picture becomes available after the draft." /></main>;

  const championship = data.champion;
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-col gap-5 px-0 py-4 sm:px-6 sm:py-8">
      <header className="space-y-2 px-1">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cfb-brand">League postseason</p>
        <h1 className="font-display text-3xl font-black italic text-cfb-text-primary sm:text-4xl">{data.is_preview ? "Playoff Picture" : "Playoffs"}</h1>
        <p className="max-w-2xl text-sm text-cfb-text-muted">{data.is_preview ? "If the season ended today" : `${data.season} postseason · ${data.status.replace(/_/g, " ")}`}</p>
      </header>
      <LeagueTabs leagueId={parsedLeagueId} draftStatus={leagueQuery.data.draft?.status} leagueStatus={leagueQuery.data.status} />

      <section className="grid gap-px overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-border-subtle sm:grid-cols-3">
        <div className="bg-cfb-surface px-4 py-3"><p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Regular season</p><p className="mt-1 text-sm font-black text-cfb-text-primary">Weeks 1–{data.regular_season_end_week}</p></div>
        <div className="bg-cfb-surface px-4 py-3"><p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Playoffs</p><p className="mt-1 text-sm font-black text-cfb-text-primary">Weeks {data.playoff_start_week}–{data.championship_week}</p></div>
        <div className="bg-cfb-surface px-4 py-3"><p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Format</p><p className="mt-1 text-sm font-black text-cfb-text-primary">{data.playoff_teams} teams · {data.max_rounds} rounds</p></div>
      </section>

      {data.status === "REVIEW_REQUIRED" ? <div className="rounded-xl border border-amber-300/40 bg-amber-300/10 p-4 text-sm text-amber-100">Postseason result requires review after a scoring correction. {data.review_reason}</div> : null}
      {championship ? <section className="rounded-xl border border-amber-300/45 bg-amber-300/[0.06] p-4"><div className="flex items-center gap-3"><Trophy className="h-5 w-5 text-amber-200" /><div><p className="text-[10px] font-black uppercase tracking-[0.16em] text-amber-100">{data.season} league champion</p><p className="mt-1 text-lg font-black text-cfb-text-primary">{championship.team_name}</p></div></div></section> : null}

      {data.is_preview ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <div className="flex items-center justify-between border-b border-cfb-border-subtle px-4 py-3"><h2 className="text-sm font-black text-cfb-text-primary">If season ended today</h2><span className="text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">Playoff cut</span></div>
          <div className="divide-y divide-cfb-border-subtle">
            {data.seeds.map((seed, index) => <div key={seed.team_id} className={`grid grid-cols-[2rem_minmax(0,1fr)_auto_auto] items-center gap-3 px-4 py-3 ${index + 1 === data.playoff_cut_line ? "border-b-2 border-cfb-brand" : ""}`}><span className="text-sm font-black text-cfb-text-muted">{seed.seed}</span><div className="min-w-0"><p className="truncate text-sm font-bold text-cfb-text-primary">{seed.team_name}</p><p className="text-xs text-cfb-text-muted">{seed.wins}-{seed.losses}{seed.ties ? `-${seed.ties}` : ""}</p></div><span className="text-xs font-bold text-cfb-text-muted">PF</span><span className="text-sm font-black tabular-nums text-cfb-text-primary">{seed.points_for.toFixed(1)}</span></div>)}
          </div>
        </section>
      ) : (
        <section className="space-y-4">
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface px-4 py-3 text-xs text-cfb-text-muted">Seeds locked · Higher seed advances only on an exact final-score tie.</div>
          <div className="grid gap-4 lg:grid-flow-col lg:auto-cols-fr lg:grid-rows-1">
            {(data.rounds ?? []).map((round) => <section key={round.round_number} className="min-w-0 rounded-xl border border-cfb-border-subtle bg-cfb-surface p-3"><h2 className="mb-3 text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Round {round.round_number} · Week {round.week}</h2><div className="space-y-3">{data.playoff_teams === 6 && round.round_number === 1 ? <div className="rounded-lg border border-cfb-brand/25 bg-cfb-brand/[0.05] px-3 py-2 text-[10px] font-bold text-cfb-text-muted"><span className="mr-2 font-black uppercase tracking-[0.14em] text-cfb-brand">First-round byes</span>#1 {data.seeds.find((seed) => seed.seed === 1)?.team_name ?? "Seed 1"} · #2 {data.seeds.find((seed) => seed.seed === 2)?.team_name ?? "Seed 2"}</div> : null}{round.matchups.map((matchup) => <MatchupCard key={matchup.id} leagueId={parsedLeagueId} matchup={matchup} />)}</div></section>)}
          </div>
          {data.final_standings?.length ? <section className="rounded-xl border border-cfb-border-subtle bg-cfb-surface"><h2 className="border-b border-cfb-border-subtle px-4 py-3 text-sm font-black text-cfb-text-primary">Final {data.season} standings</h2><ol className="divide-y divide-cfb-border-subtle">{data.final_standings.map((row) => <li key={row.team_id} className="flex items-center gap-3 px-4 py-3"><span className="w-6 text-sm font-black text-cfb-text-muted">{row.final_place}</span><ManagerAvatar avatarUrl={row.manager_avatar_url} managerName={row.manager_name ?? row.team_name} size="xs" /><span className="min-w-0 flex-1 truncate text-sm font-bold text-cfb-text-primary">{row.team_name}</span>{row.final_place === 1 ? <Trophy className="h-4 w-4 text-amber-200" /> : null}</li>)}</ol></section> : null}
        </section>
      )}
    </main>
  );
}
