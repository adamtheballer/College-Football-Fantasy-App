import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageErrorState, PageLoadingState } from "@/components/PageState";
import { apiGet, apiPost, ApiError } from "@/lib/api";

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
  players_updated?: number;
  teams_updated?: number;
  matchups_updated?: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
};

type UnmatchedProviderRow = {
  id: number;
  provider: string;
  season: number;
  week: number;
  provider_player_id: string | null;
  provider_player_name: string | null;
  provider_team: string | null;
  reason: string;
  dedupe_hash?: string | null;
  status: string;
  mapped_player_id?: number | null;
  resolved_by_user_id?: number | null;
  resolved_at?: string | null;
  raw_json: Record<string, unknown>;
  created_at?: string | null;
};

type ProviderIdentityReport = {
  missing_provider_ids?: Array<Record<string, unknown>>;
  duplicate_name_school_pairs?: Array<Record<string, unknown>>;
  identity_audits?: Array<Record<string, unknown>>;
};

type CorrectionAudit = {
  id: number;
  league_id: number;
  affected_league_ids: number[];
  player_id: number;
  source_stat_id: number | null;
  old_fantasy_points: number;
  new_fantasy_points: number;
  reason?: string | null;
  created_by_user_id?: number | null;
  created_at?: string | null;
};

type CorrectionPreview = {
  status: string;
  player_id: number;
  player_name: string;
  position: string;
  old_fantasy_points: number;
  new_fantasy_points: number;
  delta: number;
  normalized_stats: Record<string, unknown>;
  breakdown: Record<string, unknown>;
};

type ScoringRunsResponse = { data: ScoringRun[] };
type UnmatchedRowsResponse = { data: UnmatchedProviderRow[] };
type CorrectionAuditsResponse = { data: CorrectionAudit[] };
type JsonObject = Record<string, unknown>;

type AdminActionResult = Record<string, unknown>;

const statInputPlaceholder = '{"PassingYards": 250, "PassingTouchdowns": 2}';

export const parseCorrectionStats = (value: string): Record<string, unknown> => {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Stats must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
};

export const canRunLeagueWeekAction = (leagueId: string) => Number.isInteger(Number(leagueId)) && Number(leagueId) > 0;

const JsonPanel = ({ title, data }: { title: string; data: unknown }) => (
  <section className="rounded-[1.75rem] border border-white/10 bg-slate-950/45 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">{title}</p>
    <pre className="mt-4 max-h-[420px] overflow-auto rounded-2xl border border-slate-700/70 bg-black/35 p-4 text-xs leading-5 text-slate-300">
      {JSON.stringify(data, null, 2)}
    </pre>
  </section>
);

const ActionButton = ({
  children,
  disabled,
  onClick,
  tone = "primary",
}: {
  children: string;
  disabled?: boolean;
  onClick: () => void;
  tone?: "primary" | "warning" | "danger" | "neutral";
}) => {
  const toneClass =
    tone === "danger"
      ? "border-red-300/30 bg-red-400/10 text-red-100 hover:bg-red-400/20"
      : tone === "warning"
      ? "border-amber-300/30 bg-amber-300/10 text-amber-100 hover:bg-amber-300/20"
      : tone === "neutral"
      ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
      : "border-sky-300/30 bg-sky-300/10 text-sky-100 hover:bg-sky-300/20";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-2xl border px-4 py-2 text-[10px] font-black uppercase tracking-[0.16em] transition disabled:cursor-not-allowed disabled:opacity-40 ${toneClass}`}
    >
      {children}
    </button>
  );
};

const readError = (error: unknown) => (error instanceof Error ? error.message : String(error));

export default function AdminScoring() {
  const queryClient = useQueryClient();
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState(1);
  const [leagueId, setLeagueId] = useState("");
  const [provider, setProvider] = useState("manual");
  const [mapPlayerByRow, setMapPlayerByRow] = useState<Record<number, string>>({});
  const [correctionPlayerId, setCorrectionPlayerId] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionStatsText, setCorrectionStatsText] = useState(statInputPlaceholder);
  const [formError, setFormError] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<AdminActionResult | null>(null);
  const [lastPreview, setLastPreview] = useState<CorrectionPreview | null>(null);

  const parsedLeagueId = canRunLeagueWeekAction(leagueId) ? Number(leagueId) : null;

  const invalidateAdminData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin", "scoring"] }),
      queryClient.invalidateQueries({ queryKey: ["admin", "ops"] }),
    ]);
  };

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
    queryFn: () => apiGet<ProviderIdentityReport>("/admin/scoring/provider-identity", { season, week }),
    retry: false,
  });

  const unmatchedQuery = useQuery({
    queryKey: ["admin", "scoring", "unmatched", season, week],
    queryFn: () => apiGet<UnmatchedRowsResponse>("/admin/scoring/unmatched-provider-rows", { season, week, limit: 100 }),
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
        league_id: parsedLeagueId ?? undefined,
        limit: 100,
      }),
    retry: false,
  });

  const reconciliationQuery = useQuery({
    queryKey: ["admin", "scoring", "league-week", leagueId, season, week],
    enabled: parsedLeagueId !== null,
    queryFn: () => apiGet<JsonObject>(`/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}`, { season }),
    retry: false,
  });

  const lockReadinessQuery = useQuery({
    queryKey: ["admin", "scoring", "lock-readiness", leagueId, season, week, provider],
    queryFn: () =>
      apiGet<JsonObject>("/admin/scoring/lock-readiness", {
        season,
        week,
        provider,
        league_id: parsedLeagueId ?? undefined,
      }),
    retry: false,
  });

  const correctionAuditQuery = useQuery({
    queryKey: ["admin", "scoring", "correction-audits", leagueId, season, week],
    enabled: parsedLeagueId !== null,
    queryFn: () => apiGet<CorrectionAuditsResponse>(`/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}/stat-corrections`, { season, limit: 50 }),
    retry: false,
  });

  const rerunMutation = useMutation({
    mutationFn: () => {
      if (parsedLeagueId === null) throw new Error("Enter a valid league ID first.");
      return apiPost<AdminActionResult>(`/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}/rerun`, {}, { season, provider });
    },
    onSuccess: async (data) => {
      setLastAction(data);
      await invalidateAdminData();
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () => {
      if (parsedLeagueId === null) throw new Error("Enter a valid league ID first.");
      return apiPost<AdminActionResult>(`/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}/finalize`, { season });
    },
    onSuccess: async (data) => {
      setLastAction(data);
      await invalidateAdminData();
    },
  });

  const mapRowMutation = useMutation({
    mutationFn: ({ rowId, playerId }: { rowId: number; playerId: number }) =>
      apiPost<AdminActionResult>(`/admin/scoring/unmatched-provider-rows/${rowId}/map`, { player_id: playerId, match_confidence: 100 }),
    onSuccess: async (data) => {
      setLastAction(data);
      await invalidateAdminData();
    },
  });

  const rowStatusMutation = useMutation({
    mutationFn: ({ rowId, action }: { rowId: number; action: "ignore" | "resolve" }) =>
      apiPost<AdminActionResult>(`/admin/scoring/unmatched-provider-rows/${rowId}/${action}`, {}),
    onSuccess: async (data) => {
      setLastAction(data);
      await invalidateAdminData();
    },
  });

  const previewCorrectionMutation = useMutation({
    mutationFn: () => {
      if (parsedLeagueId === null) throw new Error("Enter a valid league ID first.");
      const playerId = Number(correctionPlayerId);
      if (!Number.isInteger(playerId) || playerId <= 0) throw new Error("Enter a valid correction player ID.");
      const stats = parseCorrectionStats(correctionStatsText);
      return apiPost<CorrectionPreview>(
        `/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}/stat-corrections/preview`,
        { player_id: playerId, stats },
        { season }
      );
    },
    onMutate: () => setFormError(null),
    onSuccess: (data) => {
      setLastPreview(data);
      setLastAction(data as unknown as AdminActionResult);
    },
    onError: (error) => setFormError(readError(error)),
  });

  const applyCorrectionMutation = useMutation({
    mutationFn: () => {
      if (parsedLeagueId === null) throw new Error("Enter a valid league ID first.");
      const playerId = Number(correctionPlayerId);
      if (!Number.isInteger(playerId) || playerId <= 0) throw new Error("Enter a valid correction player ID.");
      const stats = parseCorrectionStats(correctionStatsText);
      return apiPost<AdminActionResult>(
        `/admin/scoring/leagues/${parsedLeagueId}/weeks/${week}/stat-corrections`,
        { player_id: playerId, stats, reason: correctionReason || undefined },
        { season }
      );
    },
    onMutate: () => setFormError(null),
    onSuccess: async (data) => {
      setLastAction(data);
      await invalidateAdminData();
    },
    onError: (error) => setFormError(readError(error)),
  });

  const latestRuns = runsQuery.data?.data ?? [];
  const openUnmatchedRows = useMemo(() => (unmatchedQuery.data?.data ?? []).filter((row) => row.status === "open"), [unmatchedQuery.data]);
  const actionError =
    rerunMutation.error ??
    finalizeMutation.error ??
    mapRowMutation.error ??
    rowStatusMutation.error ??
    previewCorrectionMutation.error ??
    applyCorrectionMutation.error;

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
          Repair provider identity, rerun scoring, finalize weeks, preview stat changes, apply corrections, and audit outcomes.
        </p>
      </div>

      <section className="grid gap-4 rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5 md:grid-cols-4">
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Season
          <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" type="number" value={season} onChange={(event) => setSeason(Number(event.target.value))} />
        </label>
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Week
          <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" type="number" value={week} onChange={(event) => setWeek(Number(event.target.value))} />
        </label>
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          League ID
          <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" value={leagueId} onChange={(event) => setLeagueId(event.target.value)} placeholder="Required for repair actions" />
        </label>
        <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Rerun Provider
          <select className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="manual">manual</option>
            <option value="sportsdata">sportsdata</option>
            <option value="espn">espn</option>
          </select>
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
            void correctionAuditQuery.refetch();
            void opsQuery.refetch();
            void failedJobsQuery.refetch();
            void auditQuery.refetch();
          }}
        />
      ) : null}

      {runsQuery.isLoading ? <PageLoadingState title="Loading scoring runs" description="Fetching scoring worker telemetry and provider audit data." /> : null}

      {actionError || formError ? (
        <section className="rounded-[1.5rem] border border-red-300/25 bg-red-950/30 p-4 text-sm font-bold text-red-100">{formError || readError(actionError)}</section>
      ) : null}

      {lastAction ? (
        <section className="rounded-[1.5rem] border border-emerald-300/25 bg-emerald-300/10 p-4">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-200">Last Action Result</p>
          <pre className="mt-3 max-h-52 overflow-auto text-xs text-emerald-50">{JSON.stringify(lastAction, null, 2)}</pre>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-4">
        {latestRuns.slice(0, 4).map((run) => (
          <div key={run.id} className="rounded-[1.5rem] border border-white/10 bg-slate-950/45 p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{run.provider} · week {run.week}</p>
            <p className="mt-2 text-2xl font-black text-slate-50">{run.status}</p>
            <p className="mt-2 text-xs font-semibold text-slate-400">fetched {run.rows_fetched} · matched {run.rows_matched} · unmatched {run.rows_unmatched} · retries {run.retry_count}</p>
            {run.error_message ? <p className="mt-2 text-xs text-red-200">{run.error_message}</p> : null}
          </div>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">League Week Actions</p>
          <p className="mt-2 text-sm font-semibold text-slate-400">Use these after provider data is loaded or corrected. Requires a league ID.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <ActionButton disabled={parsedLeagueId === null || rerunMutation.isPending} onClick={() => rerunMutation.mutate()}>
              Rerun Scoring
            </ActionButton>
            <ActionButton disabled={parsedLeagueId === null || finalizeMutation.isPending} onClick={() => finalizeMutation.mutate()} tone="warning">
              Finalize Week
            </ActionButton>
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">Correction Builder</p>
          <div className="mt-4 grid gap-3 md:grid-cols-[160px_1fr]">
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
              Player ID
              <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" value={correctionPlayerId} onChange={(event) => setCorrectionPlayerId(event.target.value)} placeholder="123" />
            </label>
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
              Reason
              <input className="mt-2 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder="Provider box score correction" />
            </label>
          </div>
          <label className="mt-3 block text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Corrected Stats JSON
            <textarea className="mt-2 min-h-32 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-slate-100" value={correctionStatsText} onChange={(event) => setCorrectionStatsText(event.target.value)} />
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            <ActionButton disabled={parsedLeagueId === null || previewCorrectionMutation.isPending} onClick={() => previewCorrectionMutation.mutate()} tone="neutral">
              Preview Correction
            </ActionButton>
            <ActionButton disabled={parsedLeagueId === null || applyCorrectionMutation.isPending} onClick={() => applyCorrectionMutation.mutate()} tone="danger">
              Apply Correction
            </ActionButton>
          </div>
          {lastPreview ? (
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/25 p-4 text-sm font-semibold text-slate-200">
              <p>{lastPreview.player_name} ({lastPreview.position})</p>
              <p className="mt-1 text-slate-400">{lastPreview.old_fantasy_points} → {lastPreview.new_fantasy_points} ({lastPreview.delta >= 0 ? "+" : ""}{lastPreview.delta})</p>
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">Unmatched Provider Rows</p>
            <p className="mt-2 text-sm font-semibold text-slate-400">Map rows to players, or close rows as ignored/resolved. Showing open rows first.</p>
          </div>
          <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">Open {openUnmatchedRows.length}</p>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[980px] text-left text-sm">
            <thead className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              <tr>
                <th className="px-3 py-3">Provider</th>
                <th className="px-3 py-3">Player Row</th>
                <th className="px-3 py-3">Reason</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Map Player ID</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {(unmatchedQuery.data?.data ?? []).map((row) => (
                <tr key={row.id} className={row.status === "open" ? "text-slate-100" : "text-slate-500"}>
                  <td className="px-3 py-4 font-black uppercase tracking-[0.12em] text-sky-200">{row.provider}</td>
                  <td className="px-3 py-4">
                    <p className="font-black">{row.provider_player_name || "Unknown"}</p>
                    <p className="text-xs text-slate-400">ID {row.provider_player_id || "N/A"} · {row.provider_team || "No team"}</p>
                  </td>
                  <td className="px-3 py-4 text-xs font-semibold text-slate-400">{row.reason}</td>
                  <td className="px-3 py-4 font-black uppercase tracking-[0.12em]">{row.status}</td>
                  <td className="px-3 py-4">
                    <input
                      className="w-32 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100"
                      value={mapPlayerByRow[row.id] ?? ""}
                      onChange={(event) => setMapPlayerByRow((current) => ({ ...current, [row.id]: event.target.value }))}
                      disabled={row.status !== "open"}
                      placeholder="Player ID"
                    />
                  </td>
                  <td className="px-3 py-4">
                    <div className="flex flex-wrap gap-2">
                      <ActionButton
                        disabled={row.status !== "open" || mapRowMutation.isPending || !Number(mapPlayerByRow[row.id])}
                        onClick={() => mapRowMutation.mutate({ rowId: row.id, playerId: Number(mapPlayerByRow[row.id]) })}
                      >
                        Map
                      </ActionButton>
                      <ActionButton disabled={row.status !== "open" || rowStatusMutation.isPending} onClick={() => rowStatusMutation.mutate({ rowId: row.id, action: "ignore" })} tone="warning">
                        Ignore
                      </ActionButton>
                      <ActionButton disabled={row.status !== "open" || rowStatusMutation.isPending} onClick={() => rowStatusMutation.mutate({ rowId: row.id, action: "resolve" })} tone="neutral">
                        Resolve
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
              {unmatchedQuery.data?.data?.length === 0 ? (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-sm font-bold text-slate-500">No unmatched provider rows for this filter.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-sky-300/20 bg-slate-950/45 p-5">
        <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">Correction Audit</p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              <tr><th className="px-3 py-3">Audit</th><th className="px-3 py-3">Player</th><th className="px-3 py-3">Affected Leagues</th><th className="px-3 py-3">Points</th><th className="px-3 py-3">Reason</th><th className="px-3 py-3">Created</th></tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {(correctionAuditQuery.data?.data ?? []).map((row) => (
                <tr key={row.id}>
                  <td className="px-3 py-4 font-black text-slate-100">#{row.id}</td>
                  <td className="px-3 py-4 text-slate-300">{row.player_id}</td>
                  <td className="px-3 py-4 text-slate-300">{row.affected_league_ids.join(", ") || row.league_id}</td>
                  <td className="px-3 py-4 text-slate-300">{row.old_fantasy_points} → {row.new_fantasy_points}</td>
                  <td className="px-3 py-4 text-slate-400">{row.reason || "—"}</td>
                  <td className="px-3 py-4 text-xs text-slate-500">{row.created_at || "—"}</td>
                </tr>
              ))}
              {parsedLeagueId === null ? (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-sm font-bold text-slate-500">Enter a league ID to view correction audits.</td></tr>
              ) : correctionAuditQuery.data?.data?.length === 0 ? (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-sm font-bold text-slate-500">No correction audits for this league week.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <JsonPanel title="Recent Runs Raw" data={runsQuery.data ?? { loading: runsQuery.isLoading }} />
        <JsonPanel title="Provider Identity Raw" data={identityQuery.data ?? { loading: identityQuery.isLoading }} />
        <JsonPanel title="Roster Lock Readiness" data={lockReadinessQuery.data ?? { loading: lockReadinessQuery.isLoading }} />
        <JsonPanel title="Operations Metrics" data={opsQuery.data ?? { loading: opsQuery.isLoading }} />
        <JsonPanel title="Failed Jobs" data={failedJobsQuery.data ?? { loading: failedJobsQuery.isLoading }} />
        <JsonPanel title="Audit Events" data={auditQuery.data ?? { loading: auditQuery.isLoading }} />
        <JsonPanel
          title="League Week Reconciliation Raw"
          data={
            parsedLeagueId !== null
              ? reconciliationQuery.data ?? { loading: reconciliationQuery.isLoading }
              : { message: "Enter a league ID to inspect raw stats, fantasy breakdowns, team scores, matchup scores, and corrections." }
          }
        />
      </div>
    </main>
  );
}
