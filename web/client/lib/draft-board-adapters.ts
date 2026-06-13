import type { DraftBoardParticipant, DraftBoardPick, DraftBoardPlayer, DraftBoardRoster, DraftBoardState } from "@/types/draft-board";
import type { StandaloneMockDraftRoom } from "@/types/mock-draft";
import type { Player } from "@/types/player";

const normalizeParticipantType = (value: string | null | undefined): "human" | "bot" =>
  value === "bot" ? "bot" : "human";

const mapPick = (pick: StandaloneMockDraftRoom["picks"][number]): DraftBoardPick => ({
  id: pick.id,
  overallPick: pick.overall_pick,
  roundNumber: pick.round_number,
  roundPick: pick.round_pick,
  participantId: pick.participant_id,
  participantName: pick.participant_name,
  teamName: pick.team_name,
  playerId: pick.player_id,
  playerName: pick.player_name,
  playerPosition: pick.player_position,
  playerSchool: pick.player_school,
  pickSource: pick.pick_source,
  createdAt: pick.created_at,
});

const mapParticipant = (room: StandaloneMockDraftRoom, participant: StandaloneMockDraftRoom["participants"][number]): DraftBoardParticipant => ({
  id: participant.id,
  name: participant.display_name,
  teamName: participant.team_name,
  participantType: participant.participant_type,
  userId: participant.user_id,
  draftPosition: participant.draft_position,
  isCurrent: participant.id === room.current_participant_id,
  isUser: participant.id === room.user_team_id,
});

const mapRoster = (roster: StandaloneMockDraftRoom["rosters"][number]): DraftBoardRoster => ({
  participantId: roster.participant_id,
  participantName: roster.participant_name,
  teamName: roster.team_name,
  picks: roster.picks.map(mapPick),
});

export const mapPlayersToDraftBoardPlayers = (players: Player[], draftedPlayerIds: Set<number>): DraftBoardPlayer[] =>
  players
    .filter((player) => !draftedPlayerIds.has(player.id))
    .map((player, index) => {
      const stableRank = player.boardRank ?? player.rank ?? index + 1;
      return {
        id: player.id,
        rank: stableRank,
        boardRank: stableRank,
        name: player.name,
        school: player.school,
        position: player.pos,
        projection: player.sheetProjectedSeasonPoints ?? player.projection?.fpts ?? null,
        adp: player.sheetAdp ?? player.adp ?? null,
        rosteredPercent: player.rostered ?? null,
        team: player.school,
        disabled: false,
        sourcePlayer: player,
      };
    });

export const adaptMockToDraftBoardState = (
  room: StandaloneMockDraftRoom,
  availablePlayers: DraftBoardPlayer[],
  formattedTime: string,
  secondsRemaining: number | null
): DraftBoardState => {
  const mode = room.session.mode === "single_player" ? "single_mock" : "multiplayer_mock";
  const picks = room.picks.map(mapPick);
  const rosters = room.rosters.map(mapRoster);
  const userRoster = room.rosters.find((roster) => roster.participant_id === room.user_team_id)?.picks.map(mapPick) ?? [];
  const title = mode === "single_mock" ? "Single-Player Mock Draft" : "Multiplayer Mock Draft";
  return {
    mode,
    title,
    subtitle: `Round ${room.current_round} • Pick ${room.current_round_pick} • Overall ${room.current_overall_pick}/${room.total_picks}`,
    status: room.status,
    phaseType: room.status === "intermission" ? "prestart_countdown" : room.status === "live" ? "pick_clock" : null,
    currentOverallPick: room.current_overall_pick,
    totalPicks: room.total_picks,
    currentRound: room.current_round,
    currentRoundPick: room.current_round_pick,
    currentParticipantName: room.current_participant_name,
    currentParticipantType: normalizeParticipantType(room.current_participant_type),
    currentTeamName: room.current_team_name,
    secondsRemaining,
    formattedTime,
    isUserOnClock: room.is_user_on_clock,
    isComplete: room.is_complete,
    participants: room.participants.map((participant) => mapParticipant(room, participant)),
    picks,
    rosters,
    availablePlayers,
    userRoster,
    lastPick: picks.length ? picks[picks.length - 1] : null,
  };
};

export const adaptSingleMockToDraftBoardState = adaptMockToDraftBoardState;
export const adaptMultiplayerMockToDraftBoardState = adaptMockToDraftBoardState;
