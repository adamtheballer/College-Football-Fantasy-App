import type { LeagueRosterPlayer } from "@/types/league";

export type RosterDisplayPlayer = {
  acquisition_type?: string | null;
  player_id?: number | null;
  player_name?: string | null;
  projected_points?: number | null;
  status?: string | null;
  weekly_projected_fantasy_points?: number | null;
};

export const projectionValue = (player: RosterDisplayPlayer) => {
  const value = player.projected_points ?? player.weekly_projected_fantasy_points;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};

export const isPlaceholderRosterPlayer = (player: RosterDisplayPlayer) => {
  const status = (player.status ?? "").toUpperCase();
  const acquisitionType = (player.acquisition_type ?? "").toUpperCase();
  const name = player.player_name ?? "";
  return (
    status === "EMPTY_SLOT" ||
    acquisitionType === "EMPTY_SLOT" ||
    !name.trim() ||
    /\bpreview\b/i.test(name)
  );
};

export const hasValidRosterPlayerId = (player: RosterDisplayPlayer) =>
  typeof player.player_id === "number" &&
  Number.isInteger(player.player_id) &&
  player.player_id > 0;

export const isRealRosterPlayer = (player: RosterDisplayPlayer) =>
  hasValidRosterPlayerId(player) && !isPlaceholderRosterPlayer(player);

export const canOpenRosterPlayerCard = (
  player: RosterDisplayPlayer,
  forceBlank = false
) =>
  !forceBlank &&
  isRealRosterPlayer(player);

export const rosterProjectionTotal = (
  players: RosterDisplayPlayer[],
  forceBlank = false
) => {
  if (forceBlank) return null;
  const realPlayers = players.filter(isRealRosterPlayer);
  if (realPlayers.length === 0) return null;
  return realPlayers.reduce((total, player) => total + (projectionValue(player) ?? 0), 0);
};

export const shouldBlankRoster = (
  players: RosterDisplayPlayer[],
  {
    isDemoLeague = false,
    isPreDraft = false,
    message,
  }: {
    isDemoLeague?: boolean;
    isPreDraft?: boolean;
    message?: string | null;
  } = {}
) => {
  if (isDemoLeague) return false;
  const normalizedMessage = (message ?? "").toLowerCase();
  if (
    normalizedMessage.includes("roster is empty") ||
    normalizedMessage.includes("populate after the draft") ||
    normalizedMessage.includes("complete the draft") ||
    normalizedMessage.includes("placeholder roster") ||
    normalizedMessage.includes("imports real draft results") ||
    normalizedMessage.includes("no players on this roster")
  ) {
    return true;
  }
  const realPlayers = players.filter(isRealRosterPlayer);
  return isPreDraft || realPlayers.length === 0;
};

export const visibleRosterPlayers = <Player extends RosterDisplayPlayer>(
  players: Player[],
  forceBlank = false
) => (forceBlank ? [] : players);

const EMPTY_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];

export const createEmptyRosterSlotRows = ({
  rosterSlotLimits,
  fantasyTeamId,
  fantasyTeamName,
  leagueId,
}: {
  rosterSlotLimits?: Record<string, number> | null;
  fantasyTeamId?: number | null;
  fantasyTeamName?: string | null;
  leagueId?: number | null;
}): LeagueRosterPlayer[] => {
  const rows: LeagueRosterPlayer[] = [];
  const normalizedLimits = rosterSlotLimits ?? {};

  for (const slot of EMPTY_SLOT_ORDER) {
    const count = Math.max(
      0,
      Math.floor(Number(normalizedLimits[slot] ?? (slot === "BENCH" ? normalizedLimits.BE : 0) ?? 0))
    );
    for (let index = 0; index < count; index += 1) {
      rows.push({
        id: -(rows.length + 1),
        league_id: leagueId ?? null,
        team_id: fantasyTeamId ?? undefined,
        fantasy_team_id: fantasyTeamId ?? 0,
        fantasy_team_name: fantasyTeamName ?? "Your Team",
        player_id: null,
        player_name: "N/A",
        player_school: null,
        player_position: slot,
        school: null,
        position: slot,
        slot,
        roster_slot: slot,
        status: "EMPTY_SLOT",
        acquisition_type: "EMPTY_SLOT",
        draft_pick_id: null,
        is_starter: slot !== "BENCH" && slot !== "IR",
        is_ir: slot === "IR",
        opponent: null,
        projected_points: null,
        floor: null,
        ceiling: null,
        weekly_projected_fantasy_points: null,
      });
    }
  }

  return rows;
};

export const createBlankRosterRows = ({
  players,
  rosterSlotLimits,
  fantasyTeamId,
  fantasyTeamName,
  leagueId,
}: {
  players?: LeagueRosterPlayer[] | null;
  rosterSlotLimits?: Record<string, number> | null;
  fantasyTeamId?: number | null;
  fantasyTeamName?: string | null;
  leagueId?: number | null;
}): LeagueRosterPlayer[] => {
  const configuredRows = createEmptyRosterSlotRows({
    rosterSlotLimits,
    fantasyTeamId,
    fantasyTeamName,
    leagueId,
  });

  if (configuredRows.length > 0) return configuredRows;

  return (players ?? []).map((player, index) => {
    const slot = player.slot ?? player.roster_slot ?? player.position ?? player.player_position ?? "BENCH";
    const position = player.position ?? player.player_position ?? slot;

    return {
      ...player,
      id: -(index + 1),
      league_id: leagueId ?? player.league_id ?? null,
      team_id: fantasyTeamId ?? player.team_id,
      fantasy_team_id: fantasyTeamId ?? player.fantasy_team_id,
      fantasy_team_name: fantasyTeamName ?? player.fantasy_team_name,
      player_id: null,
      player_name: "N/A",
      player_school: null,
      player_position: position,
      school: null,
      position,
      slot,
      roster_slot: slot,
      status: "EMPTY_SLOT",
      acquisition_type: "EMPTY_SLOT",
      draft_pick_id: null,
      opponent: null,
      projected_points: null,
      floor: null,
      ceiling: null,
      weekly_projected_fantasy_points: null,
    };
  });
};
