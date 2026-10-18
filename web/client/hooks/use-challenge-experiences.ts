import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import type {
  Challenge,
  Game,
  Participant,
  Pick,
} from "@/hooks/use-weekly-challenges";

export const EXPERIENCE_KINDS = [
  "fanwars",
  "millionaire",
  "creator",
  "survivor",
] as const;
export type ExperienceKind = (typeof EXPERIENCE_KINDS)[number];
export const isExperience = (kind: string): kind is ExperienceKind =>
  (EXPERIENCE_KINDS as readonly string[]).includes(kind);
export type Creator = {
  id: number;
  slug: string;
  name: string;
  description: string;
  logo_url: string | null;
  links: Record<string, string>;
  authorized: boolean;
  active: boolean;
};
export type Series = {
  id: number;
  name: string;
  season: number;
  start_week: number;
  end_week: number;
  entry_open_at: string;
  first_lock_at: string;
  active: boolean;
};
export type School = { id: number; name: string; conference: string };
export type SchoolStanding = {
  school_id: number;
  school: string;
  conference: string;
  rank: number | null;
  fan_points: number;
  accuracy: number | null;
  correct_picks: number;
  eligible_picks: number;
  active_fans: number;
  provisional: boolean;
};
export type Experience = {
  kind: ExperienceKind;
  enabled: boolean;
  season: number;
  week: number;
  entry_open_at: string;
  participants: number;
  locked_game_ids: number[];
  ineligible_player_ids: number[];
  projections: Record<number, number>;
  creator: Creator | null;
  creator_picks: Pick[] | null;
  creator_correct: number | null;
  creator_score: number | null;
  comparison: "BEAT THE CREATOR" | "TIED THE CREATOR" | "CREATOR WON" | null;
  salary_budget: number;
  salaries: { player_id: number; salary: number }[];
  correct_points: number;
  minimum_fans: number;
  schools: School[];
  allegiance: School | null;
  personal_contribution: number | null;
  personal_correct: number | null;
  your_points: number | null;
  your_rank: number | null;
  best_performer: string | null;
  player_points: Record<number, number>;
  school_week_rank: number | null;
  school_season_rank: number | null;
  school_standings: SchoolStanding[];
  rivalries: {
    a: { school: string; fan_points: number; active_fans: number };
    b: { school: string; fan_points: number; active_fans: number };
    winner: string | null;
  }[];
  series: Series | null;
  survivor_status: string | null;
  weeks_survived: number;
  remaining_survivors: number;
  eliminated: number;
  previous_picks: {
    week: number;
    team: string | null;
    opponent: string | null;
    outcome: string;
    game: Game | null;
  }[];
  corrections: string[];
};
export type Mode = {
  lock_at: string | null;
  server_now: string;
  kind: ExperienceKind;
  name: string;
  description: string;
  competitions: number[];
  participants: number;
  state: string;
};
export type ExperienceStanding = Participant & {
  rank: number;
  points: number | null;
  status: string;
  correct_picks: number | null;
  selections: Pick[] | null;
};
export type ExperienceLeaderboard = {
  challenge_id: number;
  kind: ExperienceKind;
  unit: string;
  provisional: boolean;
  total: number;
  data: ExperienceStanding[];
  your_rank: ExperienceStanding | null;
  school_standings: SchoolStanding[];
};
export type ExperienceConfig = {
  expected_version: number;
  game_ids: number[];
  player_ids: number[];
  salaries: { player_id: number; salary: number }[];
  creator_picks: Pick[];
  correct_points: number;
  minimum_fans: number;
  rivalries: [number, number][];
};
export const experiencePath = (c: { kind: Challenge["kind"]; id: number }) =>
  isExperience(c.kind)
    ? `/weekly-challenges/experiences/${c.id}`
    : `/weekly-challenges/${c.id}`;
export function useModes() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["weekly-challenges", "modes", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const value = await apiGet<Mode[]>("/weekly-challenges/modes");
      if (!Array.isArray(value))
        throw new Error("Challenge modes could not be loaded.");
      return value;
    },
    refetchInterval: 30_000,
  });
}
export function useExperiences(kind: ExperienceKind) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["weekly-challenges", "experiences", user?.id, kind],
    enabled: !!user,
    queryFn: async () => {
      const value = await apiGet<Challenge[]>(
        "/weekly-challenges/experiences",
        { kind },
      );
      if (!Array.isArray(value))
        throw new Error("Competitions could not be loaded.");
      return value;
    },
    refetchInterval: 30_000,
  });
}
