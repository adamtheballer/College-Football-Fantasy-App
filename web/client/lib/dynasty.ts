import { apiGet, apiPost } from "./api";

export type DynastyAsset = { kind: "player" | "pick"; id: number };
export type DynastyTeam = {
  id: number;
  name: string;
  owner_user_id: number | null;
};
export type DynastyPick = {
  id: number;
  season: number;
  round_number: number;
  original_team_id: number;
  owner_team_id: number;
  overall_pick: number | null;
  player_id: number | null;
};
export type DynastyTrade = {
  id: number;
  from_team_id: number;
  to_team_id: number;
  status: "pending" | "accepted" | "cancelled" | "rejected";
  assets_json: (DynastyAsset & { from_team_id: number })[];
};
export type DynastyState = {
  league_id: number;
  name: string;
  commissioner_user_id: number | null;
  invite_code: string | null;
  startup_season: number;
  current_season: number;
  roster_limit: number;
  startup_rounds: number;
  freshman_rounds: number;
  future_pick_years: number;
  draft_kind: "startup" | "freshman";
  status: "scheduled" | "drafting" | "complete" | "closed";
  pick_cursor: number;
  order: number[];
  next_pick_id: number | null;
  teams: DynastyTeam[];
  rosters: {
    id: number;
    team_id: number;
    player_id: number;
    name: string;
    position: string;
    school: string | null;
    value: DynastyPool["data"][number]["value"] | null;
  }[];
  picks: DynastyPick[];
  trades: DynastyTrade[];
  departures: {
    player_id: number;
    team_id: number;
    reason: string;
    source_url?: string;
  }[];
};
export type DynastyPool = {
  total: number;
  limit: number;
  offset: number;
  data: {
    player_id: number;
    name: string;
    school: string;
    position: string;
    entry_season: number;
    source_url: string;
    value: {
      policy_version: string;
      provisional: boolean;
      base_value: number | null;
      academic_class: string;
      class_factor: number;
      age: number | null;
      age_factor: number;
      estimate: number | null;
    };
  }[];
};
export type DynastyCreate = {
  name: string;
  season: number;
  team_count: number;
  roster_limit: number;
  startup_rounds: number;
  freshman_rounds: number;
  future_pick_years: number;
};
export type DynastyFinish = {
  team_id: number;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  playoff_finish: number | null;
};
export const dynastyApi = {
  capability: () =>
    apiGet<{ enabled: boolean; earliest_season: number; preview: boolean }>(
      "/dynasty/capabilities",
    ),
  list: () => apiGet<{ data: DynastyState[] }>("/dynasty/leagues"),
  detail: (id: number) => apiGet<DynastyState>(`/dynasty/leagues/${id}`),
  pool: (id: number, offset: number) =>
    apiGet<DynastyPool>(
      `/dynasty/leagues/${id}/pool?limit=50&offset=${offset}`,
    ),
  create: (data: DynastyCreate) =>
    apiPost<DynastyState>("/dynasty/leagues", data),
  join: (invite_code: string, team_name: string) =>
    apiPost<DynastyState>("/dynasty/join", { invite_code, team_name }),
  start: (id: number) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/start`, {}),
  pick: (id: number, pick: number, player_id: number) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/picks/${pick}`, {
      player_id,
    }),
  drop: (id: number, entry: number) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/rosters/${entry}/drop`, {}),
  trade: (
    id: number,
    from_team_id: number,
    to_team_id: number,
    give: DynastyAsset[],
    receive: DynastyAsset[],
  ) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/trades`, {
      from_team_id,
      to_team_id,
      give,
      receive,
    }),
  settle: (id: number, trade: number, action: "accept" | "cancel" | "reject") =>
    apiPost<DynastyState>(
      `/dynasty/leagues/${id}/trades/${trade}/${action}`,
      {},
    ),
  close: (id: number, results: DynastyFinish[]) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/close`, { results }),
  rollover: (id: number) =>
    apiPost<DynastyState>(`/dynasty/leagues/${id}/rollover`, {}),
  history: (id: number, season: number) =>
    apiGet<{
      season: number;
      order: number[];
      results: DynastyFinish[];
      rosters: { team_id: number; player_id: number }[];
    }>(`/dynasty/leagues/${id}/history/${season}`),
};
