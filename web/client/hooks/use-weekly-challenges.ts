import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { trackProductEvent } from "@/lib/product-analytics";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, ApiError } from "@/lib/api";

export type ChallengeKind =
  | "slate12"
  | "upset"
  | "fantasy5"
  | "lock"
  | "duels"
  | "fanwars"
  | "millionaire"
  | "creator"
  | "survivor";
export type Pick = {
  game_id?: number;
  team?: string;
  player_id?: number;
  slot?: "QB" | "RB" | "WR" | "WR1" | "WR2" | "TE" | "FLEX";
};
export type Entry = {
  id: number;
  challenge_id: number;
  user_id: number;
  revision: number;
  status: string;
  selections: Pick[];
  tiebreaker: number | null;
  submitted_at: string | null;
};
export type Game = {
  id: number;
  home_team: string;
  away_team: string;
  start_date: string | null;
  status: string | null;
  home_points: number | null;
  away_points: number | null;
};
export type PoolPlayer = {
  id: number;
  game_id: number;
  name: string;
  school: string;
  position: string;
  image_url: string | null;
};
export type Underdog = { game_id: number; team: string; points: number };
export type Config = {
  game_ids: number[];
  player_ids: number[];
  featured_game_id: number | null;
  underdogs: Underdog[];
};
export type ChallengeSponsor = {
  name: string;
  label: string;
  tagline: string;
  logo_url: string;
  youtube_url: string;
  season: number;
  week: number;
};
export type Challenge = {
  participant_count?: number;
  experience?: import("@/hooks/use-challenge-experiences").Experience | null;
  sponsor?: ChallengeSponsor | null;
  id: number;
  round_id: number;
  season?: number;
  week?: number;
  kind: ChallengeKind;
  name: string;
  state: string;
  settlement_status: string;
  version: number;
  rules_version: string;
  rules: string;
  lock_at: string | null;
  server_now: string;
  published_at: string | null;
  games: Game[];
  players: PoolPlayer[];
  featured_game_id: number | null;
  underdogs: Underdog[];
  entry: Entry | null;
  scoring_version: string | null;
  scoring_rules: Record<string, unknown> | null;
  cancellation_reason: string | null;
  draft_config: Config | null;
};
export type Round = {
  sponsor?: ChallengeSponsor | null;
  id: number;
  season: number;
  week: number;
  state: string;
  next_rollover_at: string;
  server_now: string;
  challenges: Challenge[];
};
export type Participant = {
  user_id: number;
  display_name: string;
  username: string | null;
  avatar_url: string | null;
  profile_url: string;
};
export type Duel = {
  id: number;
  challenge_id: number;
  inviter: Participant;
  invitee: Participant;
  status: string;
  outcome: string | null;
};
export type LeaderRow = Participant & { rank: number; points: number };
export type Leaderboard = {
  week: number | null;
  season: number;
  round_id: number | null;
  provisional: boolean;
  data: LeaderRow[];
  your_rank: LeaderRow | null;
};
export type Result = {
  participant: Participant;
  entry_id: number;
  raw_points: number | null;
  challenge_points: number | null;
  rank: number | null;
  status: string;
  tiebreaker_error: number | null;
  selections: Pick[] | null;
};
export type Results = {
  challenge_id: number;
  state: string;
  data: Result[];
  total: number;
  limit: number;
  offset: number;
  my_result: Result | null;
};
export const CHALLENGE_NAMES: Record<ChallengeKind, string> = {
  slate12: "Slate 12",
  upset: "Upset Hunter",
  fantasy5: "Fantasy Five",
  lock: "Lock of the Week",
  duels: "Rivalry Duels",
  fanwars: "College Football Fan Wars",
  millionaire: "Fantasy Millionaire",
  creator: "Beat the Creator",
  survivor: "Last Fan Standing",
};
export const FORMATS: Record<ChallengeKind, string> = {
  slate12: "12 winners · 1 point each",
  upset: "3 underdogs · up to 15 points",
  fantasy5: "QB, RB, WR, TE + FLEX · placement points",
  lock: "One winner · 5 points",
  duels: "5 shared games · head-to-head",
  fanwars: "Represent Your School",
  millionaire: "$100 virtual budget · six players",
  creator: "Ten picks · beat an approved creator",
  survivor: "One pick · survive another week",
};
export const deadlineText = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(new Date(value))
    : "Deadline available when published";
/** Presentation only. Server time, rather than the device's wall clock, anchors the cutoff. */
export function useChallengeState(challenge?: {
  state: string;
  server_now: string;
  lock_at: string | null;
}) {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    setElapsed(false);
    if (challenge?.state !== "Open" || !challenge.lock_at) return;
    const remaining =
      Date.parse(challenge.lock_at) - Date.parse(challenge.server_now);
    if (remaining <= 0) {
      setElapsed(true);
      return;
    }
    if (remaining > 2_147_483_647) return;
    const timer = setTimeout(() => setElapsed(true), remaining);
    return () => clearTimeout(timer);
  }, [challenge?.state, challenge?.server_now, challenge?.lock_at]);
  return challenge?.state === "Open" && elapsed
    ? "Closed — Live"
    : (challenge?.state ?? "Upcoming");
}
export function challengeError(error: unknown): string {
  if (
    error instanceof ApiError &&
    error.detail &&
    typeof error.detail === "object" &&
    "message" in error.detail
  )
    return String(error.detail.message);
  return error instanceof Error
    ? error.message
    : "Unable to save. Your choices have been kept; try again before the deadline.";
}
export function useCurrentChallenges(enabled = true) {
  const { user, isBootstrapping } = useAuth();
  return useQuery({
    queryKey: ["weekly-challenges", "current", user?.id],
    enabled: enabled && !!user && !isBootstrapping,
    queryFn: () =>
      apiGet<Round>("/weekly-challenges/current", {
        include_experiences: true,
      }),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
export function useChallenge(id: number) {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["weekly-challenges", "detail", user?.id, id],
    enabled: !!user && Number.isSafeInteger(id) && id > 0,
    queryFn: () => apiGet<Challenge>(`/weekly-challenges/challenges/${id}`),
    staleTime: 5_000,
    refetchInterval: 30_000,
  });
  useEffect(() => {
    if (user && query.data)
      void trackProductEvent(user.id, "challenge_view", id);
  }, [user?.id, query.data?.id, id]);
  return query;
}
