import type { LeagueRosterPlayer } from "@/types/league";

const finalStates = new Set(["final", "post"]);

const validKickoff = (value?: string | null) => {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
};

/**
 * Derive the display state from the server's provider state and the published
 * kickoff. A kickoff is enough to start fantasy scoring; it must not wait for
 * a provider play, possession, or score event.
 */
export function rosterPlayerGameState(player?: LeagueRosterPlayer, now = Date.now()) {
  const state = (player?.live_game_state ?? "").toLowerCase();
  if (finalStates.has(state) || state === "live") return state;
  const kickoff = validKickoff(player?.game_start_at);
  return kickoff !== null && kickoff <= now ? "live" : state || "unavailable";
}

export function rosterPlayerIsLive(player?: LeagueRosterPlayer, now = Date.now()) {
  const state = rosterPlayerGameState(player, now);
  return state === "live" || ["live", "stale"].includes((player?.live_scoring_status ?? "").toLowerCase());
}

export function rosterPlayerHasUpcomingKickoff(player?: LeagueRosterPlayer, now = Date.now()) {
  const state = rosterPlayerGameState(player, now);
  if (finalStates.has(state) || state === "live") return false;
  const kickoff = validKickoff(player?.game_start_at);
  return kickoff !== null && kickoff > now;
}
