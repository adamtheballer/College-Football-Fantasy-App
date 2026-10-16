import { useLayoutEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import { shouldRestrictLeagueToDraft } from "@/lib/leagueLifecycle";

const tabs = [
  { label: "Roster", path: "roster" },
  { label: "Matchup", path: "matchup" },
  { label: "Waiver Wire", path: "waivers" },
  { label: "Watchlist", path: "watchlist" },
  { label: "Chat", path: "chat" },
  { label: "Settings", path: "settings" },
];

export function LeagueTabs({
  leagueId,
  draftStatus,
  leagueStatus,
}: {
  leagueId: number;
  draftStatus?: string | null;
  leagueStatus?: string | null;
}) {
  const location = useLocation();
  const pathname = location.pathname.replace(/\/+$/, "");
  const railRef = useRef<HTMLElement>(null);
  const hasLifecycleStatus =
    draftStatus !== undefined || leagueStatus !== undefined;
  const restrictedToDraft =
    hasLifecycleStatus &&
    shouldRestrictLeagueToDraft({ draftStatus, leagueStatus });
  const visibleTabs = restrictedToDraft
    ? [{ label: "Draft", path: "lobby" }]
    : tabs;

  useLayoutEffect(() => {
    const rail = railRef.current;
    const active = rail?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!rail || !active) return;
    const bounds = rail.getBoundingClientRect();
    const tab = active.getBoundingClientRect();
    // Reveal only the horizontal rail; scrollIntoView can also move the page.
    if (tab.left < bounds.left) rail.scrollLeft += tab.left - bounds.left;
    else if (tab.right > bounds.right)
      rail.scrollLeft += tab.right - bounds.right;
  }, [pathname, restrictedToDraft]);

  return (
    <nav
      ref={railRef}
      aria-label="League sections"
      className="min-w-0 max-w-full overflow-x-auto overscroll-x-contain border-b border-cfb-border-subtle touch-pan-x [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <div
        className="flex w-max min-w-full items-stretch gap-7 px-1 sm:gap-10 md:grid md:w-full md:min-w-0 md:gap-0 md:px-0"
        style={{
          gridTemplateColumns: `repeat(${visibleTabs.length}, minmax(0, 1fr))`,
        }}
      >
        {visibleTabs.map((tab) => {
          const href = `/league/${leagueId}/${tab.path}`;
          const active =
            pathname === href ||
            (tab.path === "roster" && pathname === `/league/${leagueId}`) ||
            (tab.path === "lobby" && pathname === `/league/${leagueId}/draft`);
          return (
            <Link
              key={tab.path}
              to={href}
              aria-current={active ? "page" : undefined}
              className={`relative flex min-h-12 shrink-0 items-center px-1 text-xs font-semibold tracking-normal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 md:justify-self-center ${
                active
                  ? "text-cfb-text-primary"
                  : "text-cfb-text-muted hover:text-cfb-text-secondary"
              }`}
            >
              {tab.label}
              {active ? (
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-cfb-brand"
                />
              ) : null}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
