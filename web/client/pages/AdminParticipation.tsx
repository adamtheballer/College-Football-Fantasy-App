import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
type Metrics = {
  days: number;
  accounts: number;
  new_accounts_in_leagues: number;
  active_accounts: number;
  returning_accounts: number;
  guide_finished_accounts: number;
  challenge_viewers: number;
  challenge_starters: number;
  challenge_submitters: number;
  submitted_entries: number;
  sharers: number;
  notification_openers: number;
  review_authorizations: number;
  review_invocations: number;
  native_versions: Record<string, number>;
  events_since: string | null;
  note: string;
};
type Health = {
  season: number;
  week: number | null;
  checked_at: string;
  verified_players: number;
  awaiting_stats_or_participation: number;
  latest_fact_at: string | null;
  latest_reviewed_injury_at: string | null;
  injury_feed_status: string;
  injury_sources: Record<string, string>;
  invalid_fact_count: number;
  feed_gap_count: number;
  sample_player_ids: number[];
  status: string;
  note: string;
};
export default function AdminParticipation() {
  const { user } = useAuth();
  const [days, setDays] = useState(7);
  const [includeTests, setIncludeTests] = useState(false);
  const q = useQuery({
    queryKey: ["participation", user?.id, days, includeTests],
    enabled: !!user?.isAdmin,
    queryFn: () =>
      apiGet<Metrics>("/product/admin/participation", {
        days,
        include_test_accounts: includeTests,
      }),
  });
  const h = useQuery({
    queryKey: ["player-health", user?.id],
    enabled: !!user?.isAdmin,
    queryFn: () => apiGet<Health>("/product/admin/player-health"),
  });
  if (!user?.isAdmin) return <Navigate to="/" replace />;
  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-24">
      <PageHeader
        eyebrow="Admin"
        title="Participation & data health"
        description="Rolling-window activity, with a separate signup cohort. Events are optional and retained for 90 days."
      />
      <label className="block text-sm">
        Reporting window
        <select
          className="cfb-control ml-3 min-h-11 px-3"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          {[7, 30, 90].map((d) => (
            <option key={d} value={d}>
              {d} days
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-h-11 items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={includeTests}
          onChange={(e) => setIncludeTests(e.target.checked)}
        />
        Include test and admin accounts (excluded by default)
      </label>
      {q.isLoading && <p role="status">Loading participation…</p>}
      {q.isError && (
        <SurfaceCard>
          <p role="alert">Participation could not load.</p>
          <Button onClick={() => void q.refetch()}>Retry participation</Button>
        </SurfaceCard>
      )}
      {q.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {(
              [
                ["New accounts", "accounts"],
                ["New accounts in leagues", "new_accounts_in_leagues"],
                ["Active accounts", "active_accounts"],
                ["Returning on another day", "returning_accounts"],
                ["Guide finished or skipped", "guide_finished_accounts"],
                ["Challenge viewers", "challenge_viewers"],
                ["Started picks", "challenge_starters"],
                ["Submitted participants", "challenge_submitters"],
                ["Official entries", "submitted_entries"],
                ["Shared challenges", "sharers"],
                ["Notification opens", "notification_openers"],
                ["Review authorizations", "review_authorizations"],
                ["Native review invocations", "review_invocations"],
              ] as const
            ).map(([label, key]) => (
              <SurfaceCard key={key} padding="compact">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-2 text-2xl font-black">{q.data![key]}</p>
              </SurfaceCard>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {q.data.note}{" "}
            {q.data.events_since
              ? `Observed events since ${new Date(q.data.events_since).toLocaleString()}.`
              : "No optional usage events observed yet."}
          </p>
          <SurfaceCard>
            <h2 className="cfb-section-title">Native versions seen</h2>
            {Object.entries(q.data.native_versions).map(([v, n]) => (
              <p key={v} className="mt-2 text-sm">
                {v}: {n} accounts
              </p>
            ))}
            {!Object.keys(q.data.native_versions).length && (
              <p className="mt-2 text-sm text-muted-foreground">
                Waiting for an instrumented native build.
              </p>
            )}
          </SurfaceCard>
        </>
      )}
      {h.isLoading && <p role="status">Checking player data sources…</p>}
      {h.isError ? (
        <SurfaceCard>
          <p role="alert">Player health could not load.</p>
          <Button onClick={() => void h.refetch()}>Retry player health</Button>
        </SurfaceCard>
      ) : (
        h.data && (
          <SurfaceCard className="space-y-3">
            <h2 className="cfb-section-title">
              Player facts · Week {h.data.week ?? "Pending"}
            </h2>
            <p className="font-bold">{h.data.status.toUpperCase()}</p>
            <p className="text-sm">
              {h.data.verified_players} verified ·{" "}
              {h.data.awaiting_stats_or_participation} awaiting stats or
              participation · {h.data.feed_gap_count} source gaps ·{" "}
              {h.data.invalid_fact_count} invalid facts
            </p>
            <p className="text-sm">
              Official injury sources: {h.data.injury_feed_status}
              {h.data.latest_reviewed_injury_at
                ? ` · last updated ${new Date(h.data.latest_reviewed_injury_at).toLocaleString()}`
                : ""}
            </p>
            <p className="text-xs text-muted-foreground">
              {Object.entries(h.data.injury_sources)
                .map(([source, status]) => `${source}: ${status}`)
                .join(" · ")}
            </p>
            <p className="text-xs text-muted-foreground">
              {h.data.note} Checked{" "}
              {new Date(h.data.checked_at).toLocaleString()}.
            </p>
            {h.data.sample_player_ids.length > 0 && (
              <p className="text-xs">
                Investigate player IDs: {h.data.sample_player_ids.join(", ")}
              </p>
            )}
          </SurfaceCard>
        )
      )}
    </div>
  );
}
