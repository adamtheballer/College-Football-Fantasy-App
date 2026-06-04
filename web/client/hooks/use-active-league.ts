import { useCallback, useEffect, useState } from "react";

const ACTIVE_LEAGUE_ID_KEY = "cfb_active_league_id";

const readStoredLeagueId = (): number | null => {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ACTIVE_LEAGUE_ID_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

export function useActiveLeagueId() {
  const [activeLeagueId, setActiveLeagueIdState] = useState<number | null>(() => readStoredLeagueId());

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== ACTIVE_LEAGUE_ID_KEY) return;
      setActiveLeagueIdState(readStoredLeagueId());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setActiveLeagueId = useCallback((leagueId: number | null) => {
    setActiveLeagueIdState(leagueId);
    if (typeof window === "undefined") return;
    if (leagueId === null) {
      window.localStorage.removeItem(ACTIVE_LEAGUE_ID_KEY);
      return;
    }
    window.localStorage.setItem(ACTIVE_LEAGUE_ID_KEY, String(leagueId));
  }, []);

  return { activeLeagueId, setActiveLeagueId };
}
