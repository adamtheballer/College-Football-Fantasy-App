import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

// The confirmation is presentation-only. Keep the two-second readable hold,
// but use a slightly longer, eased reveal/retract so the full pick card never
// feels like it snaps over the draft room.
export const PICK_BANNER_MOTION = { enter: 300, hold: 2000, exit: 260 } as const;
export type ConfirmedDraftPick = {
  key: string;
  number: number;
  teamId: number;
  playerId: number;
  name: string;
  school: string;
  position: string;
  auto: boolean;
  imageUrl?: string;
};

/** Presentation only. Never advances picks, pauses timers or changes rosters. */
export function usePickConfirmation(scope: string | undefined, picks: ConfirmedDraftPick[], ownTeamId?: number | null) {
  const baseline = useRef<{ scope: string; seen: Set<string> } | null>(null);
  const [queue, setQueue] = useState<ConfirmedDraftPick[]>([]);
  const [hidden, setHidden] = useState(() => typeof document !== "undefined" && document.hidden);
  const fresh = scope && baseline.current?.scope === scope
    ? picks.filter((pick) => !baseline.current!.seen.has(pick.key)) : [];
  const pending = !hidden && (queue.length > 0 || fresh.some((pick) => pick.teamId === ownTeamId));

  useLayoutEffect(() => {
    if (!scope) return;
    if (baseline.current?.scope !== scope) {
      baseline.current = { scope, seen: new Set(picks.map((pick) => pick.key)) };
      setQueue([]); // First snapshot/re-entry is history, not a new pick event.
      return;
    }
    const unseen = picks.filter((pick) => !baseline.current!.seen.has(pick.key));
    const own: ConfirmedDraftPick[] = [];
    for (const pick of unseen) {
      baseline.current.seen.add(pick.key);
      if (pick.teamId !== ownTeamId) continue;
      const storageKey = `cff-pick-confirmation:${scope}:${pick.key}`;
      let consumed = false;
      try {
        consumed = sessionStorage.getItem(storageKey) === "1";
        sessionStorage.setItem(storageKey, "1");
      } catch { /* In-memory dedupe still works when storage is restricted. */ }
      if (!hidden && !consumed) own.push(pick);
    }
    if (own.length) setQueue((current) => [...current, ...own.sort((a, b) => a.number - b.number)]);
  }, [scope, picks, ownTeamId, hidden]);

  useEffect(() => {
    const onVisibility = () => {
      setHidden(document.hidden);
      if (document.hidden) setQueue([]); // Do not replay suspended celebration.
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const finish = useCallback((key: string) => {
    setQueue((current) => current[0]?.key === key ? current.slice(1) : current);
  }, []);
  return { pick: hidden ? undefined : queue[0], pending, finish };
}
