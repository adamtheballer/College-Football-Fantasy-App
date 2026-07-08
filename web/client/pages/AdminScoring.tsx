import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageErrorState, PageLoadingState } from "@/components/PageState";
import { apiGet, ApiError } from "@/lib/api";

type ScoringRun = {
  id: number;
  provider: string;
  season: number;
  week: number;
  league_id: number | null;
  status: string;
  rows_fetched: number;
  rows_matched: number;
  rows_unmatched: number;
  retry_count: number;
  error_message?: string | null;
};

type ScoringRunsResponse = { data: ScoringRun[] };
type JsonObject = Record<string, unknown>;

const JsonPanel = ({ title, data }: { title: string; data: unknown }) => (
  <section className="rounded-[1.75rem] border border-white/10 bg-slate-950/45 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">{title}</p>
    <pre className="mt-4 max-h-[420px] overflow-auto rounded-2xl border border-slate-700/70 bg-black/35 p-4 text-xs leading-5 text-slate-300">
      {JSON.stringify(data, null, 2)}
    </pre>
  </section>
);

export default function AdminScoring() {
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState(1);
  const [leagueId, setLeagueId] = useState("");

  const runsQuery = useQuery({
    queryKey: ["admin", "scoring", "runs", season, week],
    queryFn: () => apiGet<ScoringRunsResponse>("/admin/scoring/runs", { season, week, limit: 25 }),
    refetchInterval: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
      return failureCount < 2;
    },
  });

  const identityQuery = useQuery({
    queryKey: ["admin", "scoring", "provider-identity", season, week],
    queryFn: () => apiGet<JsonObject>("/admin/scoring/provider-identity", { season, week }),
    retry: false,
  });

  const unmatchedQuery = useQuery({
    queryKey: ["admin", "scoring", "unmatched", season, week],
    queryFn: () => apiGet<JsonObject>("/admin/scoring/unmatched-provider-rows", { season, week, limit: 100 }),
    retry: false,
  });

  const opsQuery = useQuery({
    queryKey: ["admin", "ops", "metrics"],
    queryFn: () => apiGet<JsonObject>("/admin/ops/metrics"),
    refetchInterval: 30_000,
    retry: false,
  });

  const failedJobsQuery = useQuery({
    queryKey: ["admin", "ops", "failed-jobs"],
    queryFn: () => apiGet<JsonObject>("/admin/ops/failed-jobs", { limit: 50 }),
    refetchInterval: 30_000,
    retry: false,
  });

  const auditQuery = useQuery({
    queryKey: ["admin", "ops", "audit-events", leagueId],
    queryFn: () =>
      apiGet<JsonObject>("/admin/ops/audit-events", {
        league_id: leagueId.trim() ? Number(leagueId) : undefined,
        limit: 100,
      }),
    retry: false,
  });

  const reconciliationQuery = useQuery({
    queryKey: ["admin", "scoring", "league-week", leagueId, season, week],
    enabled: leagueId.trim().length > 0,
    queryFn: () =>
      apiGet<JsonObject>(`/admin/scoring/leagues/${Number(leagueId)}/weeks/${week}`, {
        season,
      }),
    retry: false,
  });

  const adminError =
    runsQuery.error instanceof ApiError && runsQuery.error.status === 403
      ? "Admin access is required. Add your email to ADMIN_EMAILS on the backend."
      : runsQuery.error instanceof Error
      ? runsQuery.error.message
      : null;

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">Admin</p>
        <h1 className="mt-2 text-4xl font-black italic text-slate-50">Scoring Operations</h1>
        <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-400">
          Reconcile provider rows, scoring runs, player breakdowns, team totals, matchup scores, and standings.
        </p>
      </div>

      <section className="grid gap-4 rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5 md:grid-cols-3">
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Season
          <input
            className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100"
            type="number"
            value={season}
            onChange={(event) => setSeason(Number(event.target.value))}
          />
        </label>
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Week
          <input
            className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100"
            type="number"
            value={week}
            onChange={(event) => setWeek(Number(event.target.value))}
          />
        </label>
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          League ID for reconciliation
          <input
            className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100"
            value={leagueId}
            onChange={(event) => setLeagueId(event.target.value)}
            placeholder="Optional"
          />
        </label>
      </section>

      {adminError ? (
        <PageErrorState
          title="Unable to load scoring operations"
          description={adminError}
          onAction={() => {
            void runsQuery.refetch();
            void identityQuery.refetch();
            void unmatchedQuery.refetch();
            void reconciliationQuery.refetch();
            void opsQuery.refetch();
            void failedJobsQuery.refetch();
            void auditQuery.refetch();
          }}
        />
      ) : null}

      {runsQuery.isLoading ? (
        <PageLoadingState title="Loading scoring runs" description="Fetching scoring worker telemetry and provider audit data." />
      ) : null}

      <section className="grid gap-4 md:grid-cols-4">
        {(runsQuery.data?.data ?? []).slice(0, 4).map((run) => (
          <div key={run.id} className="rounded-[1.5rem] border border-white/10 bg-slate-950/45 p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              {run.provider} · week {run.week}
            </p>
            <p className="mt-2 text-2xl font-black text-slate-50">{run.status}</p>
            <p className="mt-2 text-xs font-semibold text-slate-400">
              fetched {run.rows_fetched} · matched {run.rows_matched} · unmatched {run.rows_unmatched} · retries {run.retry_count}
            </p>
            {run.error_message ? <p className="mt-2 text-xs text-red-200">{run.error_message}</p> : null}
          </div>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <JsonPanel title="Recent Runs" data={runsQuery.data ?? { loading: runsQuery.isLoading }} />
        <JsonPanel title="Provider Identity" data={identityQuery.data ?? { loading: identityQuery.isLoading }} />
        <JsonPanel title="Unmatched Provider Rows" data={unmatchedQuery.data ?? { loading: unmatchedQuery.isLoading }} />
        <JsonPanel title="Operations Metrics" data={opsQuery.data ?? { loading: opsQuery.isLoading }} />
        <JsonPanel title="Failed Jobs" data={failedJobsQuery.data ?? { loading: failedJobsQuery.isLoading }} />
        <JsonPanel title="Audit Events" data={auditQuery.data ?? { loading: auditQuery.isLoading }} />
        <JsonPanel
          title="League Week Reconciliation"
          data={
            leagueId.trim()
              ? reconciliationQuery.data ?? { loading: reconciliationQuery.isLoading }
              : { message: "Enter a league ID to inspect raw stats, fantasy breakdowns, team scores, matchup scores, and corrections." }
          }
        />
      </div>
    </main>
  );
}
