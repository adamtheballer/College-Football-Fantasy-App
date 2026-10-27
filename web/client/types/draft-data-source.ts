import type { DraftRoom } from "./draft";
import type { Player } from "./player";
import type { LeagueDetail } from "./league";
import type { useDraftPlayerPool } from "@/hooks/use-players";

/** Data seam for the existing draft screen; never a second draft layout. */
export type DraftDataSource = {
  untimed?: boolean;
  isolated?: boolean;
  paths: (id: number) => { home: string; lobby: string; roster: string };
  useLeague: (id?: number) => {
    data?: Pick<LeagueDetail, "name" | "max_teams" | "members" | "draft">;
  };
  useRoom: (id?: number) => {
    data?: DraftRoom;
    isLoading: boolean;
    error: unknown;
    failureCount: number;
    isPaused: boolean;
    refetch: () => Promise<unknown>;
  };
  usePick: (id?: number) => {
    mutateAsync: (input: {
      playerId: number;
      pickNumber: number;
      draftVersion: number;
    }) => Promise<DraftRoom>;
    isPending: boolean;
    error: unknown;
  };
  useStart: (id?: number) => {
    mutate: () => void;
    isPending: boolean;
    error: unknown;
  };
  usePool: (params?: Parameters<typeof useDraftPlayerPool>[0]) => {
    data?: { data: Player[]; total: number };
    isLoading: boolean;
    isError: boolean;
    error: unknown;
  };
};
