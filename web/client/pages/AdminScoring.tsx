import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Activity, ClipboardCheck, RefreshCw, ShieldCheck, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, apiGet, apiPost } from "@/lib/api";

type ScoringRun = {
  id: number;
  league_id: number | null;
  season: number;
  week: number;
  provider: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  players_updated: number;
  teams_updated: number;
  matchups_updated: number;
  error_message: string | null;
};

type RunsResponse = {
  data: ScoringRun[];
  total: number;
  limit: number;
  offset: number;
};

type ProviderHealthResponse = {
  sync_states: Array<{
    provider: string;
    feed: string;
    scope_key: string;
    status: string;
    last_success_at: string | null;
    error_message: string | null;
    consecutive_failures: number;
  }>;
  open_unmatched_rows: number;
  failed_scoring_runs: number;
};

type CorrectionPreview = {
  player_id: number;
  season: number;
  week: number;
  affected_league_ids: number[];
  before_stats: Record<string, unknown> | null;
  after_stats: Record<string, unknown>;
  before_scores: Record<string, number | null>;
  projected_scores: Record<string, number>;
};

type AdminActionResponse = {
  action: string;
  message: string;
  audit: { id: number; action: string; reason: string; created_at: string };
  preview?: CorrectionPreview | null;
};

type AuditRow = {
  id: number;
  action: string;
  actor_user_id: number | null;
  league_id: number | null;
  season: number | null;
  week: number | null;
  player_id: number | null;
  affected_league_ids: number[] | null;
  reason: string;
  created_at: string;
};

type PendingAdminAction = {
  label: string;
  description: string;
  execute: () => void;
};

type ScorePreviewRow = {
  leagueId: number;
  before: number | null;
  after: number | null;
  delta: number | null;
};

type StatPreviewRow = {
  key: string;
  before: string;
  after: string;
};

export const parseJsonObject = (raw: string) => {
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Stats must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
};

export const numberOrUndefined = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const formatValue = (value: unknown) => {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(1) : "—";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
};

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

export const buildScorePreviewRows = (preview: CorrectionPreview | null): ScorePreviewRow[] => {
  if (!preview) return [];
  return preview.affected_league_ids.map((leagueId) => {
    const key = String(leagueId);
    const before = preview.before_scores[key] ?? null;
    const after = preview.projected_scores[key] ?? null;
    return {
      leagueId,
      before,
      after,
      delta: before === null || after === null ? null : after - before,
    };
  });
};

export const buildStatPreviewRows = (preview: CorrectionPreview | null): StatPreviewRow[] => {
  if (!preview) return [];
  const keys = Array.from(
    new Set([
      ...Object.keys(preview.before_stats ?? {}),
      ...Object.keys(preview.after_stats ?? {}),
    ])
  ).sort((left, right) => left.localeCompare(right));
  return keys.map((key) => ({
    key,
    before: formatValue(preview.before_stats?.[key]),
    after: formatValue(preview.after_stats[key]),
  }));
};

export default function AdminScoring() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [leagueId, setLeagueId] = useState("");
  const [season, setSeason] = useState("2026");
  const [week, setWeek] = useState("1");
  const [playerId, setPlayerId] = useState("");
  const [reason, setReason] = useState("");
  const [statsJson, setStatsJson] = useState('{"PassingYards":300,"PassingTouchdowns":3}');
  const [preview, setPreview] = useState<CorrectionPreview | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAdminAction | null>(null);

  const healthQuery = useQuery({
    queryKey: ["admin", "scoring", "provider-health"],
    enabled: !!user?.isAdmin,
    queryFn: () => apiGet<ProviderHealthResponse>("/admin/scoring/provider-health"),
  });
  const runsQuery = useQuery({
    queryKey: ["admin", "scoring", "runs", "failed"],
    enabled: !!user?.isAdmin,
    queryFn: () => apiGet<RunsResponse>("/admin/scoring/runs", { status: "failed", limit: 25 }),
  });
  const historyQuery = useQuery({
    queryKey: ["admin", "scoring", "corrections"],
    enabled: !!user?.isAdmin,
    queryFn: () => apiGet<AuditRow[]>("/admin/scoring/corrections", { limit: 25 }),
  });

  const invalidateAdmin = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "scoring"] });
  };

  const mutation = useMutation({
    mutationFn: async ({ path, body }: { path: string; body: unknown }) => apiPost<AdminActionResponse>(path, body),
    onSuccess: (payload) => {
      toast({ title: "Admin action completed", description: payload.message });
      setPendingAction(null);
      invalidateAdmin();
    },
    onError: (error) => {
      toast({
        title: "Admin action failed",
        description: error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    },
  });

  const basePayload = useMemo(
    () => ({
      league_id: numberOrUndefined(leagueId),
      season: Number(season),
      week: Number(week),
      reason,
    }),
    [leagueId, reason, season, week]
  );

  const scorePreviewRows = useMemo(() => buildScorePreviewRows(preview), [preview]);
  const statPreviewRows = useMemo(() => buildStatPreviewRows(preview), [preview]);

  const reasonIsValid = reason.trim().length >= 3;
  const numericSeason = Number(season);
  const numericWeek = Number(week);
  const numericPlayerId = Number(playerId);
  const baseInputsAreValid = Number.isFinite(numericSeason) && Number.isFinite(numericWeek) && numericWeek > 0 && reasonIsValid;
  const correctionInputsAreValid = baseInputsAreValid && Number.isFinite(numericPlayerId) && numericPlayerId > 0;

  const queueAction = (action: PendingAdminAction) => {
    if (!reasonIsValid) {
      toast({
        title: "Admin reason required",
        description: "Add a clear reason before running a repair action.",
        variant: "destructive",
      });
      return;
    }
    setPendingAction(action);
  };

  const handlePreview = async () => {
    try {
      const body = {
        player_id: Number(playerId),
        season: Number(season),
        week: Number(week),
        reason,
        stats: parseJsonObject(statsJson),
      };
      const payload = await apiPost<CorrectionPreview>("/admin/scoring/corrections/preview", body);
      setPreview(payload);
      toast({ title: "Correction preview ready", description: `${payload.affected_league_ids.length} affected league(s).` });
    } catch (error) {
      toast({
        title: "Preview failed",
        description: error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const handleApply = () => {
    queueAction({
      label: "Apply stat correction",
      description: "This will update the provider stat row, recalculate every affected league, and write an audit event.",
      execute: () => {
        mutation.mutate({
          path: "/admin/scoring/corrections/apply",
          body: {
            player_id: Number(playerId),
            season: Number(season),
            week: Number(week),
            reason,
            stats: parseJsonObject(statsJson),
          },
        });
      },
    });
  };

  if (!user?.isAdmin) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <section className="rounded-[2rem] border border-red-300/25 bg-red-500/10 p-8">
          <h1 className="text-3xl font-black text-red-100">Admin access required</h1>
          <p className="mt-3 text-sm font-semibold text-red-100/75">
            Scoring repair tools are restricted to verified administrators.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">Admin Operations</p>
        <h1 className="mt-2 text-4xl font-black italic text-slate-50">Scoring Repair Tools</h1>
        <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-400">
          Controlled scoring reruns, stat corrections, reconciliation, week finalization, and provider-health inspection.
        </p>
      </div>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-[1.5rem] border border-sky-300/20 bg-sky-400/10 p-5">
          <Activity className="h-5 w-5 text-sky-200" />
          <p className="mt-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Failed Runs</p>
          <p className="mt-1 text-3xl font-black text-slate-50">{healthQuery.data?.failed_scoring_runs ?? "—"}</p>
        </div>
        <div className="rounded-[1.5rem] border border-amber-300/20 bg-amber-400/10 p-5">
          <AlertTriangle className="h-5 w-5 text-amber-200" />
          <p className="mt-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Open Unmatched Rows</p>
          <p className="mt-1 text-3xl font-black text-slate-50">{healthQuery.data?.open_unmatched_rows ?? "—"}</p>
        </div>
        <div className="rounded-[1.5rem] border border-emerald-300/20 bg-emerald-400/10 p-5">
          <ShieldCheck className="h-5 w-5 text-emerald-200" />
          <p className="mt-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Provider Feeds</p>
          <p className="mt-1 text-3xl font-black text-slate-50">{healthQuery.data?.sync_states.length ?? "—"}</p>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6">
          <h2 className="flex items-center gap-2 text-lg font-black text-slate-50">
            <Wrench className="h-5 w-5 text-sky-200" />
            Repair Inputs
          </h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Input value={leagueId} onChange={(event) => setLeagueId(event.target.value)} placeholder="League ID optional" />
            <Input value={season} onChange={(event) => setSeason(event.target.value)} placeholder="Season" />
            <Input value={week} onChange={(event) => setWeek(event.target.value)} placeholder="Week" />
          </div>
          <Input className="mt-3" value={playerId} onChange={(event) => setPlayerId(event.target.value)} placeholder="Player ID for correction/reconcile" />
          {!reasonIsValid ? (
            <p className="mt-3 rounded-2xl border border-amber-300/15 bg-amber-400/10 px-4 py-3 text-xs font-bold text-amber-100">
              A reason of at least 3 characters is required for every admin repair action.
            </p>
          ) : null}
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            aria-label="Required admin reason"
            placeholder="Required admin reason"
            className="mt-3 min-h-20 w-full rounded-2xl border border-sky-300/15 bg-slate-950/55 p-4 text-sm font-semibold text-slate-100 outline-none focus:border-sky-300/45"
          />
          <textarea
            value={statsJson}
            onChange={(event) => setStatsJson(event.target.value)}
            aria-label="Corrected stats JSON"
            className="mt-3 min-h-32 w-full rounded-2xl border border-sky-300/15 bg-slate-950/55 p-4 font-mono text-xs text-slate-100 outline-none focus:border-sky-300/45"
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={handlePreview} disabled={!correctionInputsAreValid}>
              Preview Correction
            </Button>
            <Button type="button" onClick={handleApply} disabled={mutation.isPending || !correctionInputsAreValid || !preview}>
              Apply Correction
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending || !baseInputsAreValid}
              onClick={() => {
                queueAction({
                  label: "Rerun scoring",
                  description: "This recalculates scoring for the selected league/week and records an audit event.",
                  execute: () => mutation.mutate({ path: "/admin/scoring/rerun", body: { ...basePayload, provider: "admin" } }),
                });
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Rerun Scoring
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending || !baseInputsAreValid || !basePayload.league_id}
              onClick={() => {
                queueAction({
                  label: "Reconcile league/week",
                  description: "This recomputes league totals for the selected week and records an audit event.",
                  execute: () => mutation.mutate({ path: "/admin/scoring/reconcile/league-week", body: basePayload }),
                });
              }}
            >
              Reconcile League
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending || !correctionInputsAreValid}
              onClick={() => {
                queueAction({
                  label: "Reconcile player/week",
                  description: "This recomputes every affected league for this player/week and records an audit event.",
                  execute: () => mutation.mutate({
                    path: "/admin/scoring/reconcile/player-week",
                    body: { ...basePayload, player_id: Number(playerId) },
                  }),
                });
              }}
            >
              Reconcile Player
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending || !baseInputsAreValid || !basePayload.league_id}
              onClick={() => {
                queueAction({
                  label: "Finalize week",
                  description: "This marks all matchups for the selected league/week as final.",
                  execute: () => mutation.mutate({ path: "/admin/scoring/weeks/finalize", body: basePayload }),
                });
              }}
            >
              <ClipboardCheck className="mr-2 h-4 w-4" />
              Finalize Week
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending || !baseInputsAreValid || !basePayload.league_id}
              onClick={() => {
                queueAction({
                  label: "Reopen week",
                  description: "This reopens all matchups for the selected league/week for controlled correction.",
                  execute: () => mutation.mutate({ path: "/admin/scoring/weeks/reopen", body: basePayload }),
                });
              }}
            >
              Reopen Week
            </Button>
          </div>
          {pendingAction ? (
            <div
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="admin-action-confirm-title"
              className="mt-5 rounded-3xl border border-amber-300/25 bg-amber-400/10 p-5"
            >
              <h3 id="admin-action-confirm-title" className="text-sm font-black uppercase tracking-[0.18em] text-amber-100">
                Confirm {pendingAction.label}
              </h3>
              <p className="mt-2 text-sm font-semibold text-amber-50/80">{pendingAction.description}</p>
              <p className="mt-3 text-xs font-bold text-amber-50/70">Reason: {reason.trim()}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" onClick={pendingAction.execute} disabled={mutation.isPending}>
                  Confirm Action
                </Button>
                <Button type="button" variant="outline" onClick={() => setPendingAction(null)} disabled={mutation.isPending}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6">
          <h2 className="text-lg font-black text-slate-50">Correction Preview</h2>
          {preview ? (
            <div className="mt-4 space-y-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-sky-300/10 bg-sky-400/10 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Player</p>
                  <p className="mt-1 text-xl font-black text-slate-50">#{preview.player_id}</p>
                </div>
                <div className="rounded-2xl border border-sky-300/10 bg-sky-400/10 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Week</p>
                  <p className="mt-1 text-xl font-black text-slate-50">{preview.season} · Week {preview.week}</p>
                </div>
                <div className="rounded-2xl border border-sky-300/10 bg-sky-400/10 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Affected Leagues</p>
                  <p className="mt-1 text-xl font-black text-slate-50">{preview.affected_league_ids.length}</p>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-sky-300/10">
                <div className="grid grid-cols-4 bg-slate-900/80 px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                  <span>League</span>
                  <span>Before</span>
                  <span>After</span>
                  <span>Delta</span>
                </div>
                {scorePreviewRows.map((row) => (
                  <div key={row.leagueId} className="grid grid-cols-4 border-t border-sky-300/10 px-4 py-3 text-sm font-bold text-slate-200">
                    <span>{row.leagueId}</span>
                    <span>{formatValue(row.before)}</span>
                    <span>{formatValue(row.after)}</span>
                    <span className={row.delta !== null && row.delta < 0 ? "text-red-200" : "text-emerald-200"}>
                      {row.delta === null ? "—" : `${row.delta >= 0 ? "+" : ""}${row.delta.toFixed(1)}`}
                    </span>
                  </div>
                ))}
              </div>

              <div className="overflow-hidden rounded-2xl border border-sky-300/10">
                <div className="grid grid-cols-[1fr_1fr_1fr] bg-slate-900/80 px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                  <span>Stat</span>
                  <span>Current</span>
                  <span>Corrected</span>
                </div>
                {statPreviewRows.map((row) => (
                  <div key={row.key} className="grid grid-cols-[1fr_1fr_1fr] border-t border-sky-300/10 px-4 py-3 text-sm font-bold text-slate-200">
                    <span>{row.key}</span>
                    <span>{row.before}</span>
                    <span>{row.after}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm font-semibold text-slate-500">Run a preview before applying any correction.</p>
          )}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-[2rem] border border-red-300/20 bg-red-500/5 p-6">
          <h2 className="text-lg font-black text-slate-50">Failed Scoring Runs</h2>
          <div className="mt-4 space-y-3">
            {(runsQuery.data?.data ?? []).map((run) => (
              <div key={run.id} className="rounded-2xl border border-red-300/10 bg-slate-950/50 p-4 text-sm text-slate-300">
                <p className="font-black text-red-100">Run #{run.id} · League {run.league_id ?? "Global"} · Week {run.week}</p>
                <p className="mt-1 text-xs text-red-100/70">{run.error_message ?? "No error message recorded."}</p>
                <p className="mt-2 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                  Started {formatDateTime(run.started_at)} · Provider {run.provider}
                </p>
              </div>
            ))}
            {!runsQuery.data?.data.length ? <p className="text-sm font-semibold text-slate-500">No failed scoring runs loaded.</p> : null}
          </div>
        </div>
        <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6">
          <h2 className="text-lg font-black text-slate-50">Correction History</h2>
          <div className="mt-4 space-y-3">
            {(historyQuery.data ?? []).map((row) => (
              <div key={row.id} className="rounded-2xl border border-sky-300/10 bg-slate-950/50 p-4 text-sm text-slate-300">
                <p className="font-black text-sky-100">Correction #{row.id} · Player {row.player_id} · Week {row.week}</p>
                <p className="mt-1 text-xs text-slate-400">{row.reason}</p>
              </div>
            ))}
            {!historyQuery.data?.length ? <p className="text-sm font-semibold text-slate-500">No corrections applied yet.</p> : null}
          </div>
        </div>
      </section>
    </main>
  );
}
