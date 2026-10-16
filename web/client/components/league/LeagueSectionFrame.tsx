import type { ReactNode } from "react";
import { Bell, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { useLeagueDetail } from "@/hooks/use-leagues";
import { LeagueTabs } from "./LeagueTabs";

/** Shared outside the route suspense boundary so page content cannot move the rail. */
export function LeagueSectionFrame({
  leagueId,
  sessionReady,
  fullWidth,
  children,
}: {
  leagueId: number;
  sessionReady: boolean;
  fullWidth: boolean;
  children: ReactNode;
}) {
  // Uses the pages' existing query key/cache; no second league data source.
  const { data: league } = useLeagueDetail(leagueId, sessionReady);
  const initials =
    (league?.name ?? "League")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0]?.toUpperCase() ?? "")
      .join("") || "LG";

  return (
    <div data-testid="league-section-frame" className="min-w-0 pt-1 sm:pt-4">
      {sessionReady ? (
        <>
          <header className="flex h-16 items-center gap-3 border-b border-cfb-border-subtle px-3 sm:px-5">
            <span
              aria-hidden="true"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cfb-brand/50 bg-cfb-brand/[0.1] text-[10px] font-black text-cfb-brand"
            >
              {initials}
            </span>
            <div className="min-w-0 flex-1 text-base font-black italic tracking-tight text-cfb-text-primary">
              <span className="block truncate">{league?.name ?? "League"}</span>
            </div>
            <Link
              to="/alerts"
              aria-label="Notifications"
              className="cfb-icon-button"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link to="/chats" aria-label="Messages" className="cfb-icon-button">
              <MessageCircle className="h-4 w-4" aria-hidden="true" />
            </Link>
          </header>
          <div className="px-3 sm:px-5">
            {league ? (
              <LeagueTabs
                leagueId={leagueId}
                draftStatus={league.draft?.status}
                leagueStatus={league.status}
              />
            ) : (
              <div
                className="h-12 border-b border-cfb-border-subtle"
                aria-label="Loading league navigation"
                aria-busy="true"
              />
            )}
          </div>
        </>
      ) : null}
      <div className={fullWidth ? "min-w-0" : "min-w-0 px-3 sm:px-5"}>
        {children}
      </div>
    </div>
  );
}
