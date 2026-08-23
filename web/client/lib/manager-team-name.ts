import type { LeagueMatchupTeam } from "@/types/league";

type MatchupTeamIdentity = Pick<LeagueMatchupTeam, "fantasy_team_name" | "manager_name">;

/**
 * Matchup views identify a roster by its current manager rather than a
 * historical custom team nickname. The backend keeps that nickname for
 * backwards-compatible league data, but it must not create a second visible
 * identity after a manager updates their profile name.
 */
export const managerTeamName = (
  team: MatchupTeamIdentity | null | undefined,
  fallback = "Team",
) => {
  const managerName = team?.manager_name?.trim();
  if (managerName) return `${managerName}'s Team`;

  return team?.fantasy_team_name?.trim() || fallback;
};

export const managerNameForAvatar = (
  team: MatchupTeamIdentity | null | undefined,
  fallback = "Team",
) => team?.manager_name?.trim() || team?.fantasy_team_name?.trim() || fallback;
