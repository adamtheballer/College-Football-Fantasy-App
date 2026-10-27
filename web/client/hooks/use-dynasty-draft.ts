import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { dynastyApi, type DynastyState, type DynastyPool } from "@/lib/dynasty";
import { stampDraftRoom } from "@/lib/draftReconciliation";
import type { DraftDataSource } from "@/types/draft-data-source";
import type { DraftRoom, DraftRoomPick } from "@/types/draft";
import type { Player } from "@/types/player";

const stateKey = (id: number | undefined, userId: number | undefined) =>
  ["dynasty", id, "draft-state", userId] as const;
const version = (s: DynastyState) =>
  s.pick_cursor + (s.status === "scheduled" ? 0 : 1);
const keepLatest = (current: unknown, next: unknown) => {
  const old = current as DynastyState | undefined,
    incoming = next as DynastyState;
  if (
    old &&
    (old.current_season > incoming.current_season ||
      (old.current_season === incoming.current_season &&
        (version(old) > version(incoming) ||
          Date.parse(old.server_time) > Date.parse(incoming.server_time))))
  )
    return old;
  return incoming;
};

function useStateQuery(id?: number) {
  const { user } = useAuth();
  return useQuery({
    queryKey: stateKey(id, user?.id),
    enabled: !!id && !!user,
    queryFn: ({ signal }) => dynastyApi.detail(id!, signal),
    retry: false,
    refetchInterval: 1000,
    refetchIntervalInBackground: true,
    structuralSharing: keepLatest,
  });
}

export function toDynastyDraftRoom(
  state: DynastyState,
  userId?: number,
): DraftRoom {
  const mine = state.teams.find((t) => t.owner_user_id === userId);
  const next = state.picks.find((p) => p.id === state.next_pick_id);
  const order = state.order.length ? state.order : state.teams.map((t) => t.id);
  const count = Math.max(state.teams.length, 1);
  const rounds =
    state.draft_kind === "startup"
      ? state.startup_rounds
      : state.freshman_rounds;
  const picks = state.draft_picks;
  const roster: DraftRoomPick[] = state.rosters.map((r) => ({
    id: -r.id,
    overall_pick:
      picks.find((p) => p.player_id === r.player_id)?.overall_pick ?? 0,
    round_number: 0,
    round_pick: 0,
    team_id: r.team_id,
    team_name: state.teams.find((t) => t.id === r.team_id)?.name ?? "",
    player_id: r.player_id,
    player_name: r.name,
    player_position: r.position,
    player_school: r.school ?? "School unreviewed",
    made_by_user_id: null,
    auto_pick: false,
    created_at: state.server_time,
  }));
  return {
    league_id: state.league_id,
    // UI/session identity only. Never a regular Draft ID or a mutation target.
    draft_id: -(state.league_id * 10000 + state.current_season),
    status:
      state.status === "drafting"
        ? "on_clock"
        : state.status === "closed"
          ? "complete"
          : state.status,
    pick_timer_seconds: 0,
    roster_slots: { BENCH: rounds },
    roster_capacity: { BENCH: state.roster_limit },
    roster_entries: roster,
    pick_owners: Object.fromEntries(
      state.picks
        .filter(
          (p) => p.season === state.current_season && p.overall_pick !== null,
        )
        .map((p) => [p.overall_pick!, p.owner_team_id]),
    ),
    teams: order
      .map((id) => state.teams.find((t) => t.id === id)!)
      .map((t) => ({ ...t, owner_name: null, is_cpu: false })),
    picks,
    current_pick: state.pick_cursor + 1,
    current_round: Math.floor(state.pick_cursor / count) + 1,
    current_round_pick: (state.pick_cursor % count) + 1,
    current_team_id: next?.owner_team_id ?? null,
    current_team_name:
      state.teams.find((t) => t.id === next?.owner_team_id)?.name ?? null,
    user_team_id: mine?.id ?? null,
    can_make_pick:
      state.status === "drafting" &&
      next?.owner_team_id === mine?.id &&
      !!mine &&
      state.rosters.filter((r) => r.team_id === mine.id).length <
        state.roster_limit,
    can_start_draft:
      state.status === "scheduled" &&
      state.commissioner_user_id === userId &&
      state.teams.length === state.team_count,
    pre_draft_starts_at: null,
    draft_starts_at: null,
    current_pick_started_at: null,
    current_pick_deadline: null,
    transition_ends_at: null,
    seconds_remaining: 0,
    draft_version: version(state),
    pick_started_at: null,
    pick_expires_at: null,
    server_time: state.server_time,
  };
}

export function toDynastyDraftPlayer(row: DynastyPool["data"][number]): Player {
  return {
    id: row.player_id,
    name: row.name,
    school: row.school,
    pos: row.position,
    playerClass: row.value.academic_class,
    conf: "",
    rank: row.draft_rank,
    masterDraftRank: row.draft_rank,
    draftRankingVersion: "dynasty_preview_v1",
    draftProjectedPoints: null,
    draftProjectionMissing: true,
    draftFinalScore: row.value.estimate ?? 0,
    adp: 0,
    posRank: null,
    rostered: 0,
    status: "UNREPORTED",
    projection: { fpts: 0 },
    hasWeeklyProjection: false,
    history: [],
    analysis: "",
  };
}

function useLeague(id?: number) {
  const query = useStateQuery(id);
  return {
    data: query.data
      ? {
          name: query.data.name,
          max_teams: query.data.team_count,
          members: [],
          draft: null,
        }
      : undefined,
  };
}
function useRoom(id?: number) {
  const { user } = useAuth();
  const query = useStateQuery(id);
  const data = useMemo(
    () =>
      query.data
        ? stampDraftRoom(toDynastyDraftRoom(query.data, user?.id))
        : undefined,
    [query.data, user?.id],
  );
  return { ...query, data };
}
function useWrite(id?: number) {
  const { user } = useAuth();
  const cache = useQueryClient();
  return useMutation({
    retry: false,
    onMutate: async () => {
      await cache.cancelQueries({ queryKey: stateKey(id, user?.id) });
    },
    mutationFn: async (
      input: {
        playerId: number;
        pickNumber: number;
        draftVersion: number;
      } | null,
    ) => {
      if (!id) throw new Error("Draft room is missing a valid league id.");
      const before = cache.getQueryData<DynastyState>(stateKey(id, user?.id));
      if (
        input &&
        (!before ||
          input.pickNumber !== before.pick_cursor + 1 ||
          input.draftVersion !== version(before) ||
          before.next_pick_id === null)
      )
        throw new Error("Draft state changed. Refresh before selecting.");
      const updated = input
        ? await dynastyApi.pick(id, before!.next_pick_id!, input.playerId)
        : await dynastyApi.start(id);
      cache.setQueryData(
        stateKey(id, user?.id),
        (old: DynastyState | undefined) => keepLatest(old, updated),
      );
      return stampDraftRoom(toDynastyDraftRoom(updated, user?.id));
    },
    onSettled: () => {
      void cache.invalidateQueries({ queryKey: ["dynasty", id] });
    },
  });
}
function usePick(id?: number) {
  return useWrite(id);
}
function useStart(id?: number) {
  const mutation = useWrite(id);
  return { ...mutation, mutate: () => mutation.mutate(null) };
}
function usePool(params: Parameters<DraftDataSource["usePool"]>[0]) {
  const query = useStateQuery(params?.league_id);
  return useQuery({
    queryKey: [
      "dynasty",
      params?.league_id,
      "draft-pool",
      query.data?.current_season,
      query.data?.status === "scheduled",
    ],
    enabled: !!query.data,
    retry: false,
    queryFn: async ({ signal }) => {
      const first = await dynastyApi.pool(params!.league_id!, 0, false, signal);
      const rows = [...first.data];
      for (
        let offset = first.limit;
        offset < first.total;
        offset += first.limit
      ) {
        const page = await dynastyApi.pool(
          params!.league_id!,
          offset,
          false,
          signal,
        );
        if (!page.data.length)
          throw new Error(
            "Draft pool changed while loading. Refresh the draft room.",
          );
        rows.push(...page.data);
      }
      return { data: rows.map(toDynastyDraftPlayer), total: first.total };
    },
  });
}
export const dynastyDraftSource: DraftDataSource = {
  untimed: true,
  isolated: true,
  paths: (id) => ({
    home: `/labs/dynasty?league=${id}`,
    lobby: `/labs/dynasty?league=${id}`,
    roster: `/labs/dynasty?league=${id}`,
  }),
  useLeague,
  useRoom,
  usePick,
  useStart,
  usePool,
};
