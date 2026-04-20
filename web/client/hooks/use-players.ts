import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { Player } from "@/types/player";

type BackendPlayerRead = {
  id: number;
  name: string;
  position: string;
  school: string;
  image_url?: string | null;
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

const VALID_STATUSES = new Set(["HEALTHY", "OUT", "QUESTIONABLE", "DOUBTFUL", "IR"]);

const normalizeStatus = (value?: string | null): Player["status"] => {
  if (!value) return "HEALTHY";
  const normalized = value.toUpperCase();
  if (VALID_STATUSES.has(normalized)) return normalized as Player["status"];
  if (normalized === "PROBABLE") return "HEALTHY";
  return "HEALTHY";
};

const mapProjection = (projection?: BackendProjectionRead): Player["projection"] => ({
  fpts: projection?.fantasy_points ?? 0,
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
    posRank?: number;
    status?: string;
    projection?: BackendProjectionRead;
  }
): Player => ({
  id: player.id,
  name: player.name,
  school: player.school,
  pos: player.position,
  imageUrl: player.image_url ?? undefined,
  conf: context?.conference ?? "N/A",
  rank: context?.rank ?? 0,
  adp: context?.adp ?? 0,
  posRank: context?.posRank ?? 0,
  rostered: 0,
  status: normalizeStatus(context?.status),
  projection: mapProjection(context?.projection),
  history: [],
  analysis: "",
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

      const projectionByPlayerId = new Map<number, BackendProjectionRead>();
      const overallRankByPlayer = new Map<number, number>();
      const posRankByPlayer = new Map<number, number>();

      const sortedProjections = [...projections.data].sort((a, b) => b.fantasy_points - a.fantasy_points);
      const positionCounters = new Map<string, number>();
      sortedProjections.forEach((row, index) => {
        projectionByPlayerId.set(row.player_id, row);
        overallRankByPlayer.set(row.player_id, index + 1);
      });

      payload.data.forEach((player) => {
        const projection = projectionByPlayerId.get(player.id);
        if (!projection) return;
        const current = positionCounters.get(player.position) ?? 0;
        const nextRank = current + 1;
        positionCounters.set(player.position, nextRank);
        posRankByPlayer.set(player.id, nextRank);
      });

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
            rank: overallRankByPlayer.get(player.id) ?? 0,
            adp: overallRankByPlayer.get(player.id) ?? 0,
            posRank: posRankByPlayer.get(player.id) ?? 0,
            status: injuryByPlayerId.get(player.id),
            projection: projectionByPlayerId.get(player.id),
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
        posRank: 0,
        status: injuryByPlayerId.get(payload.id),
        projection,
      });
    },
  });
}
