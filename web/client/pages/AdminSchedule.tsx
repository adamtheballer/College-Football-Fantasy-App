import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Clock3, RefreshCw, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, apiGet, apiPost, apiPut } from "@/lib/api";

type ScheduleIssue = {
  id: number;
  team_name: string;
  opponent_name: string | null;
  issue_type: string;
  current_value: string | null;
  provider_value: string | null;
  source: string;
  confidence: number | null;
  notes: string | null;
  updated_at: string;
};

type ScheduleSyncSummary = {
  source: string;
  games_fetched: number;
  games_matched: number;
  games_updated: number;
  games_still_missing_time: number;
  skipped_manual_override: number;
  skipped_low_confidence: number;
  issues: Record<string, number>;
};

const readableIssue = (issueType: string) => issueType.replaceAll("_", " ");

export default function AdminSchedule() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [season, setSeason] = useState("2026");
  const [week, setWeek] = useState("2");
  const [overrideScheduleId, setOverrideScheduleId] = useState("");
  const [overrideKickoff, setOverrideKickoff] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const numericSeason = Number(season);
  const numericWeek = Number(week);
  const scheduleScopeValid = Number.isInteger(numericSeason) && Number.isInteger(numericWeek) && numericWeek >= 0;

  const issuesQuery = useQuery({
    queryKey: ["admin", "schedules", "issues", numericSeason, numericWeek],
    enabled: !!user?.isAdmin && scheduleScopeValid,
    queryFn: () => apiGet<ScheduleIssue[]>("/admin/schedules/issues", { season_year: numericSeason, week: numericWeek }),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "schedules"] });

  const syncMutation = useMutation({
    mutationFn: () => apiPost<ScheduleSyncSummary>("/admin/schedules/sync", {
      season_year: numericSeason,
      week: numericWeek,
      source: "auto",
      force_current_week: true,
    }),
    onSuccess: (summary) => {
      toast({ title: "Schedule sync completed", description: `${summary.games_updated} schedule row(s) updated from ${summary.source}.` });
      invalidate();
    },
    onError: (error) => toast({
      title: "Schedule sync failed",
      description: error instanceof ApiError ? error.message : "No changes were committed. Review provider availability and retry.",
      variant: "destructive",
    }),
  });

  const overrideMutation = useMutation({
    mutationFn: () => {
      const kickoff = new Date(overrideKickoff);
      if (!Number.isFinite(kickoff.getTime())) throw new Error("Enter a valid kickoff time.");
      return apiPut(`/admin/schedules/${Number(overrideScheduleId)}/kickoff`, {
        kickoff_at: kickoff.toISOString(),
        reason: overrideReason.trim(),
      });
    },
    onSuccess: () => {
      toast({ title: "Manual kickoff saved", description: "Provider retries will preserve this reviewed override." });
      setOverrideScheduleId("");
      setOverrideKickoff("");
      setOverrideReason("");
      invalidate();
    },
    onError: (error) => toast({
      title: "Manual override failed",
      description: error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Try again.",
      variant: "destructive",
    }),
  });

  if (!user?.isAdmin) {
    return <main className="mx-auto max-w-5xl px-6 py-10"><section className="rounded-[2rem] border border-red-300/25 bg-red-500/10 p-8"><h1 className="text-3xl font-black text-red-100">Admin access required</h1></section></main>;
  }

  const validOverride = Number.isInteger(Number(overrideScheduleId)) && Number(overrideScheduleId) > 0 && overrideKickoff && overrideReason.trim().length >= 3;
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div>
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">Admin Operations</p>
        <h1 className="mt-2 text-4xl font-black italic text-slate-50">Schedule Time Sync</h1>
        <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-400">Reconcile only exact provider matches. Confirmed times are never replaced by blank data, and overrides stay protected.</p>
      </div>

      <section className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input aria-label="Schedule season" value={season} onChange={(event) => setSeason(event.target.value)} placeholder="Season" />
            <Input aria-label="Schedule week" value={week} onChange={(event) => setWeek(event.target.value)} placeholder="Week" />
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => void issuesQuery.refetch()} disabled={issuesQuery.isFetching || !scheduleScopeValid}>
              <RefreshCw className={`mr-2 h-4 w-4 ${issuesQuery.isFetching ? "animate-spin" : ""}`} /> Refresh issues
            </Button>
            <Button type="button" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending || !scheduleScopeValid}>
              <Clock3 className="mr-2 h-4 w-4" /> Run verified sync
            </Button>
          </div>
        </div>
        <p className="mt-3 text-xs font-semibold text-slate-500">The production lifecycle worker also retries this scope Tuesday–Saturday. This action records a durable audit trail and does not guess a kickoff.</p>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6">
          <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-lg font-black text-slate-50"><AlertTriangle className="h-5 w-5 text-amber-200" /> Open schedule issues</h2><span className="text-sm font-black text-sky-200">{issuesQuery.data?.length ?? "—"}</span></div>
          {issuesQuery.isError ? <p className="mt-4 text-sm font-bold text-red-200">Unable to load schedule issues.</p> : null}
          {!issuesQuery.isLoading && !issuesQuery.isError && !(issuesQuery.data?.length) ? <p className="mt-4 text-sm font-semibold text-emerald-200">No unresolved schedule rows for this scope.</p> : null}
          <div className="mt-4 space-y-3">
            {issuesQuery.data?.map((issue) => <article key={issue.id} className="rounded-2xl border border-amber-300/15 bg-amber-400/5 p-4">
              <p className="text-sm font-black text-slate-100">{issue.team_name} <span className="text-slate-500">vs.</span> {issue.opponent_name ?? "opponent"}</p>
              <p className="mt-1 text-xs font-black uppercase tracking-[0.14em] text-amber-100">{readableIssue(issue.issue_type)} · {issue.source}</p>
              <p className="mt-2 text-xs font-semibold text-slate-400">{issue.notes ?? "Review this row before applying a manual time."}</p>
            </article>)}
          </div>
        </div>

        <form className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 p-6" onSubmit={(event) => { event.preventDefault(); if (validOverride) overrideMutation.mutate(); }}>
          <h2 className="flex items-center gap-2 text-lg font-black text-slate-50"><Wrench className="h-5 w-5 text-sky-200" /> Reviewed manual override</h2>
          <p className="mt-2 text-sm font-semibold text-slate-400">Use only after verifying the provider/official school source. The override is applied to both sides of the linked game.</p>
          <Input className="mt-4" aria-label="Schedule row ID" value={overrideScheduleId} onChange={(event) => setOverrideScheduleId(event.target.value)} placeholder="Schedule row ID" inputMode="numeric" />
          <Input className="mt-3" aria-label="Verified kickoff" value={overrideKickoff} onChange={(event) => setOverrideKickoff(event.target.value)} type="datetime-local" />
          <textarea className="mt-3 min-h-24 w-full rounded-2xl border border-sky-300/15 bg-slate-950/55 p-4 text-sm font-semibold text-slate-100 outline-none focus:border-sky-300/45" aria-label="Override reason" value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} placeholder="Required verification reason" />
          <Button className="mt-4 w-full" type="submit" disabled={!validOverride || overrideMutation.isPending}>Save protected override</Button>
        </form>
      </section>
    </main>
  );
}
