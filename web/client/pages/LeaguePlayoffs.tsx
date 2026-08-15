import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Brackets, RefreshCw, ShieldCheck, Trophy } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import {
  useLeagueDetail,
  useLeaguePlayoffBracket,
  useLeaguePlayoffSeeding,
  useLockLeaguePlayoffSeeding,
  useReconcileLeaguePlayoffs,
} from "@/hooks/use-leagues";
import { ApiError } from "@/lib/api";
import type { PlayoffBracketMatchup, PlayoffSeed } from "@/types/league";

const labelForCriterion = (value: string) => value.replace(/_/g, " ");

const record = (seed: PlayoffSeed) => {
  const { wins, losses, ties } = seed.record;
  return ties ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
};

const teamLabel = (team: { team_name: string | null; seed: number | null }) =>
  team.team_name ? `#${team.seed ?? "?"} ${team.team_name}` : "Awaiting winner";

function BracketGame({ matchup }: { matchup: PlayoffBracketMatchup }) {
  return (
    <article className="min-w-[220px] rounded-2xl border border-cyan-200/15 bg-slate-950/45 p-3 shadow-[0_12px_30px_rgba(2,6,23,0.25)]">
      <div className="mb-2 flex items-center justify-between gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
        <span>Week {matchup.week}</span>
        <span>{matchup.status.replace(/_/g, " ")}</span>
      </div>
      {[matchup.team_a, matchup.team_b].map((team, index) => {
        const advanced = team.team_id && team.team_id === matchup.advancing_team_id;
        return (
          <div key={index} className={`flex items-center justify-between rounded-xl px-2.5 py-2 text-sm font-bold ${advanced ? "bg-emerald-300/15 text-emerald-100" : "text-slate-300"}`}>
            <span className="truncate">{teamLabel(team)}</span>
            {advanced ? <Trophy className="h-3.5 w-3.5 shrink-0" /> : null}
          </div>
        );
      })}
      {matchup.tiebreaker_used ? <p className="mt-2 text-[10px] font-semibold text-amber-200">Tied playoff: higher original seed advanced.</p> : null}
    </article>
  );
}

export default function LeaguePlayoffs() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const { user } = useAuth();
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const seedingQuery = useLeaguePlayoffSeeding(parsedLeagueId);
  const bracketQuery = useLeaguePlayoffBracket(parsedLeagueId);
  const lockMutation = useLockLeaguePlayoffSeeding(parsedLeagueId);
  const reconcileMutation = useReconcileLeaguePlayoffs(parsedLeagueId);
  const [actionError, setActionError] = useState<string | null>(null);
  const isCommissioner = leagueQuery.data?.commissioner_user_id === user?.id;
  const bracketByRound = useMemo(() => {
    const groups = new Map<number, PlayoffBracketMatchup[]>();
    for (const matchup of bracketQuery.data?.rounds ?? []) {
      groups.set(matchup.round_number, [...(groups.get(matchup.round_number) ?? []), matchup]);
    }
    return [...groups.entries()].sort(([left], [right]) => left - right);
  }, [bracketQuery.data?.rounds]);

  const runAction = async (action: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "The playoff update could not be completed.");
    }
  };

  if (leagueQuery.isLoading) return <main className="mx-auto w-full max-w-[1320px] px-6 py-8 text-sm text-slate-400">Loading playoffs…</main>;
  if (leagueQuery.isError) return <main className="mx-auto w-full max-w-[1320px] px-6 py-8"><ErrorState title="Unable to load playoffs" message="The league could not be loaded." onRetry={() => void leagueQuery.refetch()} /></main>;

  const seedingError = seedingQuery.error instanceof ApiError && seedingQuery.error.status === 409 ? seedingQuery.error.message : null;
  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-cyan-300">League Postseason</p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Playoffs</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">Server-locked seeds use record, points for, fair head-to-head, best weekly score, and a persisted lot only when necessary.</p>
          </div>
          {isCommissioner ? <div className="flex flex-wrap gap-2">
            {!bracketQuery.data ? <Button disabled={lockMutation.isPending || Boolean(seedingError)} onClick={() => void runAction(() => lockMutation.mutateAsync())}><ShieldCheck />{lockMutation.isPending ? "Locking…" : "Lock seeding"}</Button> : null}
            {bracketQuery.data ? <Button variant="outline" disabled={reconcileMutation.isPending} onClick={() => void runAction(() => reconcileMutation.mutateAsync())}><RefreshCw />{reconcileMutation.isPending ? "Reconciling…" : "Reconcile certified games"}</Button> : null}
          </div> : null}
        </div>
        <LeagueTabs leagueId={parsedLeagueId} draftStatus={leagueQuery.data?.draft?.status} leagueStatus={leagueQuery.data?.status} />
      </header>

      {actionError ? <ErrorState title="Playoff action was not applied" message={actionError} /> : null}
      {seedingError ? <section className="rounded-2xl border border-amber-300/25 bg-amber-300/10 p-5 text-sm text-amber-100"><p className="font-bold">Seeding is not ready to lock.</p><p className="mt-1">{seedingError}</p></section> : null}

      {seedingQuery.data ? <section className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-slate-950/60">
        <div className="border-b border-cyan-200/10 p-5"><h2 className="flex items-center gap-2 text-xl font-black text-slate-50"><Trophy className="h-5 w-5 text-cyan-200" />Seeding {seedingQuery.data.state === "SEEDING_LOCKED" ? "locked" : "preview"}</h2><p className="mt-1 text-sm text-slate-400">Top {seedingQuery.data.playoff_team_count} qualify. Regular-season ties remain part of each record.</p></div>
        <div className="divide-y divide-cyan-200/10">{seedingQuery.data.entries.map((seed) => <div key={seed.team_id} className={`grid gap-2 px-4 py-3 text-sm sm:grid-cols-[64px_minmax(0,1fr)_100px_120px] sm:items-center ${seed.qualified ? "bg-cyan-300/[0.045]" : "text-slate-500"}`}><span className="font-black text-cyan-100">#{seed.seed}</span><span className="min-w-0 truncate font-bold text-slate-100">{seed.team_name}{seed.qualified ? "" : " · eliminated"}</span><span>{record(seed)}</span><span className="text-xs uppercase tracking-wide text-slate-400">{labelForCriterion(seed.resolved_by)}</span></div>)}</div>
      </section> : null}

      {bracketQuery.data ? <section className="overflow-hidden rounded-[2rem] border border-violet-300/20 bg-[linear-gradient(135deg,rgba(15,23,42,0.96),rgba(30,27,75,0.88))] p-4 sm:p-6">
        <div className="mb-5 flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-xl font-black text-white"><Brackets className="h-5 w-5 text-violet-200" />Championship bracket</h2><p className="mt-1 text-sm text-slate-400">{bracketQuery.data.status.replace(/_/g, " ")}</p></div></div>
        <div className="flex snap-x gap-4 overflow-x-auto pb-3">{bracketByRound.map(([round, games]) => <div key={round} className="min-w-[240px] flex-1 snap-start space-y-3"><p className="text-[10px] font-black uppercase tracking-[0.16em] text-violet-200">{games[0]?.round_type.replace(/_/g, " ")}</p>{games.map((game) => <BracketGame key={`${round}-${game.slot_number}`} matchup={game} />)}</div>)}</div>
      </section> : <section className="rounded-[2rem] border border-slate-700 bg-slate-950/55 p-8 text-center"><h2 className="text-xl font-black text-slate-100">Bracket not locked</h2><p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">Managers can see the authoritative seeding preview once every regular-season matchup is certified. Only the commissioner can lock it.</p><Link className="mt-4 inline-block text-sm font-bold text-cyan-200 hover:text-cyan-100" to={`/league/${parsedLeagueId}/settings`}>View league standings →</Link></section>}
    </main>
  );
}
