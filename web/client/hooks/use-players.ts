import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { Player } from "@/types/player";

type BackendPlayerRead = {
  id: number;
  name: string;
  position: string;
  school: string;
};

type BackendPlayerListResponse = {
  data: BackendPlayerRead[];
  total: number;
  limit: number;
  offset: number;
};

export const normalizePlayer = (player: BackendPlayerRead): Player => ({
  id: player.id,
  name: player.name,
  school: player.school,
  pos: player.position,
  conf: "UNKNOWN",
  rank: 0,
  adp: 0,
  posRank: 0,
  rostered: 0,
  status: "HEALTHY",
  projection: { fpts: 0 },
  history: [],
  analysis:
    "Backend player profile loaded. Projection and roster-specific context will appear as supporting contracts come online.",
});

export function usePlayers(
  params: {
    search?: string;
    position?: string;
    school?: string;
    limit?: number;
    offset?: number;
  } = {}
) {
  const { search, position, school, limit = 100, offset = 0 } = params;

  return useQuery({
    queryKey: ["players", { search: search || "", position: position || "", school: school || "", limit, offset }],
    staleTime: 30_000,
    queryFn: async () => {
      const payload = await apiGet<BackendPlayerListResponse>("/players", {
        search: search || undefined,
        position: position || undefined,
        school: school || undefined,
        limit,
        offset,
      });
      return {
        ...payload,
        data: payload.data.map(normalizePlayer),
      };
    },
  });
}

export function usePlayerDetail(playerId?: number | null, enabled = true) {
  return useQuery({
    queryKey: ["player", playerId],
    enabled: enabled && typeof playerId === "number" && !Number.isNaN(playerId),
    staleTime: 30_000,
    queryFn: async () => {
      const payload = await apiGet<BackendPlayerRead>(`/players/${playerId}`);
      return normalizePlayer(payload);
    },
  });
}
