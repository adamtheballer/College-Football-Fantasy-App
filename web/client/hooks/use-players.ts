import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { Player } from "@/types/player";

type BackendPlayerRead = {
  id: number;
  name: string;
  position: string;
  school: string;
  image_url?: string | null;
  player_class?: string | null;
  sheet_adp?: number | null;
  sheet_projected_season_points?: number | null;
  sheet_projection_stats?: Record<string, number | null> | null;
  sheet_source_sheet_id?: string | null;
  sheet_synced_at?: string | null;
  board_rank?: number | null;
};

type BackendPlayerListResponse = {
  data: BackendPlayerRead[];
  total: number;
  limit: number;
  offset: number;
};

type BackendProjectionRead = {
  player_id: number;
  pass_yards: number;
  pass_tds: number;
  interceptions: number;
  rush_yards: number;
  rush_tds: number;
  rec_yards: number;
  rec_tds: number;
  receptions: number;
  fantasy_points: number;
  floor: number;
  ceiling: number;
  boom_prob: number;
  bust_prob: number;
  qb_rating?: number | null;
  expected_plays: number;
  expected_rush_per_play: number;
  expected_td_per_play: number;
};

type BackendProjectionListResponse = {
  data: BackendProjectionRead[];
};

type BackendTeamSummary = {
  team: string;
  conference: string;
};

type BackendTeamSummaryResponse = {
  data: BackendTeamSummary[];
};

type BackendInjuryRow = {
  player_id: number;
  status: string;
};

type BackendInjuryResponse = {
  data: BackendInjuryRow[];
};

export type PlayerSeasonStatsResponse = {
  player_id: number;
  season: number;
  week: number;
  source: string;
  cached: boolean;
  stats: Record<string, unknown> | null;
  message?: string | null;
};

export type PlayerCardResponse = {
  player: BackendPlayerRead;
  about: {
    espn_player_id?: string | null;
    height?: string | null;
    weight?: string | null;
    player_class?: string | null;
    birthplace?: string | null;
    status?: string | null;
    jersey?: string | null;
    position?: string | null;
    team?: string | null;
    headshot_url?: string | null;
    source: string;
    message?: string | null;
  };
  injuries: Array<{
    id: number;
    season: number;
    week: number;
    status: string;
    injury?: string | null;
    return_timeline?: string | null;
    practice_level?: string | null;
    is_game_time_decision: boolean;
    is_returning: boolean;
    notes?: string | null;
    updated_at: string;
  }>;
  season_stats: Array<{
    season: number;
    week: number;
    source: string;
    stats: Record<string, unknown>;
    updated_at: string;
  }>;
};

const VALID_STATUSES = new Set(["HEALTHY", "OUT", "QUESTIONABLE", "DOUBTFUL", "IR"]);

const normalizeStatus = (value?: string | null): Player["status"] => {
  if (!value) return "HEALTHY";
  const normalized = value.toUpperCase();
  if (VALID_STATUSES.has(normalized)) return normalized as Player["status"];
  if (normalized === "PROBABLE") return "HEALTHY";
  return "HEALTHY";
};

const mapProjection = (
  projection?: BackendProjectionRead,
  fallbackFantasyPoints = 0
): Player["projection"] => ({
  fpts: projection?.fantasy_points ?? fallbackFantasyPoints,
  passingYards: projection?.pass_yards ?? 0,
  passingTds: projection?.pass_tds ?? 0,
  ints: projection?.interceptions ?? 0,
  rushingYards: projection?.rush_yards ?? 0,
  rushingTds: projection?.rush_tds ?? 0,
  receptions: projection?.receptions ?? 0,
  receivingYards: projection?.rec_yards ?? 0,
  receivingTds: projection?.rec_tds ?? 0,
  floor: projection?.floor ?? 0,
  ceiling: projection?.ceiling ?? 0,
  boomProb: projection?.boom_prob ?? 0,
  bustProb: projection?.bust_prob ?? 0,
  qbr: projection?.qb_rating ?? undefined,
  expectedPlays: projection?.expected_plays ?? 0,
  expectedRushPerPlay: projection?.expected_rush_per_play ?? 0,
  expectedTdPerPlay: projection?.expected_td_per_play ?? 0,
});

export const normalizePlayer = (
  player: BackendPlayerRead,
  context?: {
    conference?: string;
    rank?: number;
    adp?: number;
    posRank?: number | null;
    status?: string;
    projection?: BackendProjectionRead;
  }
): Player => ({
  id: player.id,
  name: player.name,
  school: player.school,
  pos: player.position,
  imageUrl: player.image_url ?? undefined,
  playerClass: player.player_class ?? undefined,
  conf: context?.conference ?? "N/A",
  rank: context?.rank ?? player.board_rank ?? player.sheet_adp ?? 0,
  boardRank: player.board_rank ?? player.sheet_adp ?? context?.rank ?? null,
  adp: context?.adp ?? player.sheet_adp ?? 0,
  posRank: context?.posRank ?? null,
  rostered: 0,
  status: normalizeStatus(context?.status),
  projection: mapProjection(context?.projection, player.sheet_projected_season_points ?? 0),
  history: [],
  analysis: "",
  sheetAdp: player.sheet_adp ?? undefined,
  sheetProjectedSeasonPoints: player.sheet_projected_season_points ?? undefined,
  sheetProjectionStats: player.sheet_projection_stats ?? undefined,
  sheetSourceSheetId: player.sheet_source_sheet_id ?? undefined,
  sheetSyncedAt: player.sheet_synced_at ?? undefined,
});

export function usePlayers(
  params: {
    search?: string;
    position?: string;
    school?: string;
    league_id?: number;
    available_only?: boolean;
    sort?: string;
    season?: number;
    week?: number;
    limit?: number;
    offset?: number;
  } = {}
) {
  const {
    search,
    position,
    school,
    league_id,
    available_only,
    sort,
    season = new Date().getFullYear(),
    week = 1,
    limit = 100,
    offset = 0,
  } = params;

  return useQuery({
    queryKey: [
      "players",
      {
        search: search || "",
        position: position || "",
        school: school || "",
        league_id: league_id || 0,
        available_only: available_only ? "true" : "false",
        sort: sort || "",
        season,
        week,
        limit,
        offset,
      },
    ],
    staleTime: 30_000,
    queryFn: async () => {
      const [payload, projections, teams, injuries] = await Promise.all([
        apiGet<BackendPlayerListResponse>("/players", {
          search: search || undefined,
          position: position || undefined,
          school: school || undefined,
          league_id,
          available_only,
          sort,
          limit,
          offset,
        }),
        apiGet<BackendProjectionListResponse>("/projections", {
          season,
          week,
          limit: 2000,
          offset: 0,
        }).catch(
          (): BackendProjectionListResponse => ({
            data: [],
          })
        ),
        apiGet<BackendTeamSummaryResponse>("/stats/teams", {
          season,
          conference: "ALL",
        }).catch(
          (): BackendTeamSummaryResponse => ({
            data: [],
          })
        ),
        apiGet<BackendInjuryResponse>("/stats/injuries", {
          season,
          week,
          conference: "ALL",
        }).catch(
          (): BackendInjuryResponse => ({
            data: [],
          })
        ),
      ]);

      const overallRankByPlayer = new Map<number, number>();

      const sortedProjections = [...projections.data].sort((a, b) => b.fantasy_points - a.fantasy_points);
      sortedProjections.forEach((row, index) => {
        overallRankByPlayer.set(row.player_id, index + 1);
      });
      const projectionByPlayerId = new Map<number, BackendProjectionRead>(
        projections.data.map((row) => [row.player_id, row])
      );

      const conferenceEntries: Array<[string, string]> = teams.data.map(
        (row): [string, string] => [row.team.toUpperCase(), row.conference]
      );
      const injuryEntries: Array<[number, string]> = injuries.data.map(
        (row): [number, string] => [row.player_id, row.status]
      );
      const conferenceBySchool = new Map<string, string>(conferenceEntries);
      const injuryByPlayerId = new Map<number, string>(injuryEntries);

      return {
        ...payload,
        data: payload.data.map((player) =>
          normalizePlayer(player, {
            conference: conferenceBySchool.get(player.school.toUpperCase()) ?? "N/A",
            rank: player.board_rank ?? player.sheet_adp ?? overallRankByPlayer.get(player.id) ?? 0,
            adp: player.sheet_adp ?? player.board_rank ?? overallRankByPlayer.get(player.id) ?? 0,
            posRank: null,
            status: injuryByPlayerId.get(player.id),
            projection: projectionByPlayerId.get(player.id),
          })
        ),
      };
    },
  });
}

export function useDraftPlayerPool(
  params: {
    search?: string;
    position?: string;
    school?: string;
    league_id?: number;
    available_only?: boolean;
    sort?: string;
    limit?: number;
    offset?: number;
    pages?: number;
  } = {}
) {
  const {
    search,
    position,
    school,
    league_id,
    available_only,
    sort,
    limit = 100,
    offset = 0,
    pages = 1,
  } = params;

  return useQuery({
    queryKey: [
      "draft-player-pool",
      {
        search: search || "",
        position: position || "",
        school: school || "",
        league_id: league_id || 0,
        available_only: available_only ? "true" : "false",
        sort: sort || "",
        limit,
        offset,
        pages,
      },
    ],
    staleTime: 15_000,
    queryFn: async () => {
      const fetchPage = (pageOffset: number) =>
        apiGet<BackendPlayerListResponse>("/players", {
          search: search || undefined,
          position: position || undefined,
          school: school || undefined,
          league_id,
          available_only,
          sort,
          limit,
          offset: pageOffset,
        });

      const [firstPayload, teams] = await Promise.all([
        fetchPage(offset),
        apiGet<BackendTeamSummaryResponse>("/stats/teams", {
          season: new Date().getFullYear(),
          conference: "ALL",
        }).catch(
          (): BackendTeamSummaryResponse => ({
            data: [],
          })
        ),
      ]);
      const pageCount = Math.max(1, pages);
      const remainingOffsets = Array.from({ length: pageCount - 1 }, (_, index) => offset + limit * (index + 1));
      const remainingPayloads = remainingOffsets.length
        ? await Promise.all(remainingOffsets.map((pageOffset) => fetchPage(pageOffset)))
        : [];
      const rows = [firstPayload, ...remainingPayloads].flatMap((payload) => payload.data);
      const conferenceBySchool = new Map(
        teams.data.map((row): [string, string] => [row.team.toUpperCase(), row.conference])
      );

      return {
        ...firstPayload,
        limit: limit * pageCount,
        data: rows.map((player) =>
          normalizePlayer(player, {
            conference: conferenceBySchool.get(player.school.toUpperCase()) ?? "N/A",
            rank: player.board_rank ?? player.sheet_adp ?? 0,
            adp: player.sheet_adp ?? player.board_rank ?? 0,
            posRank: null,
          })
        ),
      };
    },
  });
}

export function usePlayerDetail(playerId?: number | null, enabled = true) {
  const season = new Date().getFullYear();
  const week = 1;
  return useQuery({
    queryKey: ["player", playerId, season, week],
    enabled: enabled && typeof playerId === "number" && !Number.isNaN(playerId),
    staleTime: 30_000,
    queryFn: async () => {
      const [payload, projection, teams, injuries] = await Promise.all([
        apiGet<BackendPlayerRead>(`/players/${playerId}`),
        apiGet<BackendProjectionRead>(`/projections/${playerId}`, { season, week }).catch(() => undefined),
        apiGet<BackendTeamSummaryResponse>("/stats/teams", {
          season,
          conference: "ALL",
        }).catch(
          (): BackendTeamSummaryResponse => ({
            data: [],
          })
        ),
        apiGet<BackendInjuryResponse>("/stats/injuries", {
          season,
          week,
          conference: "ALL",
        }).catch(
          (): BackendInjuryResponse => ({
            data: [],
          })
        ),
      ]);

      const conferenceEntries: Array<[string, string]> = teams.data.map(
        (row): [string, string] => [row.team.toUpperCase(), row.conference]
      );
      const injuryEntries: Array<[number, string]> = injuries.data.map(
        (row): [number, string] => [row.player_id, row.status]
      );
      const conferenceBySchool = new Map<string, string>(conferenceEntries);
      const injuryByPlayerId = new Map<number, string>(injuryEntries);

      return normalizePlayer(payload, {
        conference: conferenceBySchool.get(payload.school.toUpperCase()) ?? "N/A",
        rank: 0,
        adp: 0,
        posRank: null,
        status: injuryByPlayerId.get(payload.id),
        projection,
      });
    },
  });
}

export function usePlayerCard(playerId?: number | null, enabled = true) {
  return useQuery({
    queryKey: ["player-card", playerId],
    enabled: enabled && typeof playerId === "number" && !Number.isNaN(playerId),
    staleTime: 60_000,
    queryFn: () => apiGet<PlayerCardResponse>(`/players/${playerId}/card`),
  });
}

export function usePlayerSeasonStats(
  playerId?: number | null,
  season = 2025,
  enabled = true
) {
  return useQuery({
    queryKey: ["player-season-stats", playerId, season],
    enabled: enabled && typeof playerId === "number" && !Number.isNaN(playerId),
    staleTime: 60_000,
    queryFn: () =>
      apiGet<PlayerSeasonStatsResponse>(`/players/${playerId}/season-stats`, {
        season,
      }),
  });
}
