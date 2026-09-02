import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { ErrorState } from "@/components/states";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";

import Chats from "./Chats";

/**
 * The league-level route composes the existing chat surface instead of
 * maintaining a second implementation. It locks the shared component to this
 * league and keeps the league rail present while managers read or post.
 */
export default function LeagueChat() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });

  if (!Number.isInteger(parsedLeagueId) || parsedLeagueId <= 0) {
    return <Navigate to="/leagues" replace />;
  }

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-0 py-4 sm:px-6 sm:py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league chat...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8">
        <ErrorState
          title="Unable to load league"
          message="The league could not be loaded. Confirm the backend is available, then try again."
          retryLabel="Try Again"
          onRetry={() => void leagueQuery.refetch()}
        />
      </main>
    );
  }

  if (!postDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/lobby`} replace />;
  }

  return (
    <main className="relative mx-auto flex w-full max-w-none flex-col gap-6 px-0 py-4 sm:py-8">
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">
          League Chat
        </p>
        <div>
          <h1 className="cfb-display-title text-3xl text-cfb-text-primary sm:text-4xl">
            Chat
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm text-cfb-text-secondary">
            Talk with your league, coordinate trades, and follow official league
            activity.
          </p>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>
      <Chats leagueId={parsedLeagueId} embedded />
    </main>
  );
}
