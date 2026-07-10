import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRightLeft, Check, ChevronRight, Clock3, Search, ShieldAlert, Users, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import {
  useLeagueDetail,
  useLeagues,
  useLeagueSettingsTab,
  useLeagueWorkspace,
} from "@/hooks/use-leagues";
import { useLeagueTeams, useTeamRoster } from "@/hooks/use-teams";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeagueRosterPlayer } from "@/types/league";
import type { RosterEntry } from "@/types/roster";
import type { Team } from "@/types/team";

const OFFENSE_POSITIONS = new Set(["QB", "RB", "WR", "TE", "K"]);

type TradeAnalyzePayload = {
  receive_ids: number[];
  give_ids: number[];
  season: number;
  week: number;
  league_size: number;
  roster_slots: Record<string, number>;
};

type TradeAnalyzeResult = {
  receive_value: number;
  give_value: number;
  delta: number;
  verdict: string;
};

type TradeOfferItemCreate = {
  player_id: number;
};

type TradeOfferCreatePayload = {
  proposing_team_id: number;
  receiving_team_id: number;
  proposing_items: TradeOfferItemCreate[];
  receiving_items: TradeOfferItemCreate[];
  message?: string | null;
};

type TradeOfferItem = {
  id: number;
  trade_offer_id: number;
  team_id: number;
  player_id: number | null;
  draft_pick_id: number | null;
};

type TradeReview = {
  id: number;
  trade_offer_id: number;
  reviewer_user_id: number | null;
  action: string;
  reason: string | null;
  created_at: string;
};

type TradeOffer = {
  id: number;
  league_id: number;
  proposing_team_id: number;
  receiving_team_id: number;
  status: string;
  expires_at: string | null;
  message: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  items: TradeOfferItem[];
  reviews: TradeReview[];
};

type TradeOfferListResponse = {
  data: TradeOffer[];
  total: number;
};

type TradeRow = {
  rosterEntryId: number;
  playerId: number;
  teamId: number;
  teamName?: string | null;
  name: string;
  position: string;
  school: string;
  slot: string;
  projectedPoints?: number;
};

export const canSubmitTradeOffer = (
  ownedTeamId: number | null,
  opponentTeamId: number | null,
  giveIds: number[],
  receiveIds: number[]
) =>
  typeof ownedTeamId === "number" &&
  ownedTeamId > 0 &&
  typeof opponentTeamId === "number" &&
  opponentTeamId > 0 &&
  ownedTeamId !== opponentTeamId &&
  giveIds.length > 0 &&
  receiveIds.length > 0;

export const buildTradeOfferPayload = ({
  ownedTeamId,
  opponentTeamId,
  giveIds,
  receiveIds,
  message,
}: {
  ownedTeamId: number | null;
  opponentTeamId: number | null;
  giveIds: number[];
  receiveIds: number[];
  message?: string;
}): TradeOfferCreatePayload => {
  if (!canSubmitTradeOffer(ownedTeamId, opponentTeamId, giveIds, receiveIds)) {
    throw new Error("Select at least one player from each team before sending a trade.");
  }
  return {
    proposing_team_id: ownedTeamId,
    receiving_team_id: opponentTeamId,
    proposing_items: giveIds.map((playerId) => ({ player_id: playerId })),
    receiving_items: receiveIds.map((playerId) => ({ player_id: playerId })),
    message: message?.trim() || null,
  };
};

export const tradeStatusLabel = (status: string) => {
  const normalized = status.toLowerCase();
  if (normalized === "proposed") return "Pending";
  if (normalized === "commissioner_review") return "Accepted · Commissioner Review";
  return normalized.replace(/_/g, " ");
};

const POS_STYLES: Record<string, string> = {
  QB: "bg-blue-500/20 border-blue-400/30 text-blue-300",
  RB: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300",
  WR: "bg-violet-500/20 border-violet-400/30 text-violet-300",
  TE: "bg-amber-500/20 border-amber-400/30 text-amber-300",
  K: "bg-cyan-500/20 border-cyan-400/30 text-cyan-300",
};

const toTradeRows = (entries: RosterEntry[] | undefined): TradeRow[] => {
  if (!entries?.length) return [];
  return entries
    .filter((entry) => OFFENSE_POSITIONS.has((entry.player.position ?? "").toUpperCase()))
    .map((entry) => ({
      rosterEntryId: entry.id,
      playerId: entry.player.id,
      teamId: entry.team_id,
      name: entry.player.name,
      position: entry.player.position.toUpperCase(),
      school: entry.player.school,
      slot: (entry.slot || "BENCH").toUpperCase(),
    }))
    .sort((a, b) => {
      const starterA = a.slot !== "BENCH" ? 0 : 1;
      const starterB = b.slot !== "BENCH" ? 0 : 1;
      if (starterA !== starterB) return starterA - starterB;
      return a.name.localeCompare(b.name);
    });
};

const toTradeRowsFromLeagueRoster = (entries: LeagueRosterPlayer[] | undefined): TradeRow[] => {
  if (!entries?.length) return [];
  return entries
    .filter((entry) => {
      const position = (entry.player_position ?? entry.position ?? "").toUpperCase();
      return entry.player_id !== null && OFFENSE_POSITIONS.has(position);
    })
    .map((entry) => ({
      rosterEntryId: entry.id,
      playerId: Number(entry.player_id),
      teamId: entry.fantasy_team_id ?? entry.team_id ?? 0,
      teamName: entry.fantasy_team_name,
      name: entry.player_name,
      position: (entry.player_position ?? entry.position ?? "").toUpperCase(),
      school: entry.player_school ?? entry.school ?? "",
      slot: (entry.roster_slot ?? entry.slot ?? "BENCH").toUpperCase(),
      projectedPoints: entry.projected_points ?? entry.weekly_projected_fantasy_points ?? 0,
    }))
    .filter((entry) => entry.teamId > 0)
    .sort((a, b) => {
      const starterA = a.slot !== "BENCH" ? 0 : 1;
      const starterB = b.slot !== "BENCH" ? 0 : 1;
      if (starterA !== starterB) return starterA - starterB;
      return a.name.localeCompare(b.name);
    });
};

const mergeProjectedValues = (rows: TradeRow[], fallbackRows: TradeRow[]): TradeRow[] => {
  if (!rows.length || !fallbackRows.length) return rows;
  const fallbackByTeamPlayer = new Map(
    fallbackRows.map((row) => [`${row.teamId}:${row.playerId}`, row])
  );
  return rows.map((row) => {
    const fallback = fallbackByTeamPlayer.get(`${row.teamId}:${row.playerId}`);
    return fallback
      ? {
          ...row,
          teamName: row.teamName ?? fallback.teamName,
          projectedPoints: row.projectedPoints ?? fallback.projectedPoints,
        }
      : row;
  });
};

const toTradeRosterSlots = (slots: Record<string, number> | undefined): Record<string, number> => {
  if (!slots) {
    return { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BE: 4, IR: 1 };
  }
  return {
    QB: Number(slots.QB ?? 1),
    RB: Number(slots.RB ?? 2),
    WR: Number(slots.WR ?? 2),
    TE: Number(slots.TE ?? 1),
    K: Number(slots.K ?? 1),
    BE: Number(slots.BENCH ?? slots.BE ?? 4),
    IR: Number(slots.IR ?? 1),
  };
};

const TradeList = ({
  title,
  subtitle,
  rows,
  selectedIds,
  onToggle,
}: {
  title: string;
  subtitle: string;
  rows: TradeRow[];
  selectedIds: Set<number>;
  onToggle: (playerId: number) => void;
}) => {
  if (!rows.length) {
    return (
      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-primary">
            {title}
          </CardTitle>
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
            {subtitle}
          </p>
        </CardHeader>
        <CardContent className="pb-8">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
            No offensive players found on this roster.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-[2rem] border border-white/10 bg-card/40">
      <CardHeader>
        <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-primary">
          {title}
        </CardTitle>
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
          {subtitle}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.map((row) => {
          const selected = selectedIds.has(row.playerId);
          return (
            <button
              key={row.rosterEntryId}
              type="button"
              onClick={() => onToggle(row.playerId)}
              className={cn(
                "w-full rounded-2xl border px-4 py-3 text-left transition-all",
                selected
                  ? "border-primary/40 bg-primary/10"
                  : "border-white/10 bg-white/[0.03] hover:border-white/20"
              )}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black italic uppercase tracking-tight text-foreground">
                    {row.name}
                  </p>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/60">
                    {row.school} • {row.slot}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-xl border px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em]",
                    POS_STYLES[row.position] ?? POS_STYLES.QB
                  )}
                >
                  {row.position}
                </span>
              </div>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default function Trade() {
  const { leagueId: leagueIdParam, playerId: playerIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: leagues = [] } = useLeagues(50, true);
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();

  const parsedLeagueId =
    leagueIdParam && /^\d+$/.test(leagueIdParam) ? Number(leagueIdParam) : undefined;
  const fallbackLeagueId = activeLeagueId ?? leagues[0]?.id;
  const leagueId = parsedLeagueId ?? fallbackLeagueId;

  const { data: league } = useLeagueDetail(leagueId, Boolean(leagueId));
  const { data: workspace } = useLeagueWorkspace(leagueId, Boolean(leagueId));
  const { data: teamsPayload } = useLeagueTeams(leagueId, Boolean(leagueId));
  const { data: settingsView } = useLeagueSettingsTab(leagueId, Boolean(leagueId));

  const teams = teamsPayload?.data ?? [];
  const ownedTeamId =
    workspace?.owned_team?.id ??
    teams.find((team) => team.owner_user_id && team.owner_user_id === user?.id)?.id ??
    null;
  const opponentTeams = useMemo(
    () => teams.filter((team) => team.id !== ownedTeamId),
    [ownedTeamId, teams]
  );
  const allLeagueRosterRows = useMemo(
    () => toTradeRowsFromLeagueRoster(settingsView?.rosters),
    [settingsView?.rosters]
  );
  const fallbackRowsByTeam = useMemo(() => {
    const rowsByTeam = new Map<number, TradeRow[]>();
    allLeagueRosterRows.forEach((row) => {
      rowsByTeam.set(row.teamId, [...(rowsByTeam.get(row.teamId) ?? []), row]);
    });
    return rowsByTeam;
  }, [allLeagueRosterRows]);

  const [opponentTeamId, setOpponentTeamId] = useState<number | null>(null);
  const [giveIds, setGiveIds] = useState<number[]>([]);
  const [receiveIds, setReceiveIds] = useState<number[]>([]);
  const [playerSearch, setPlayerSearch] = useState("");
  const [analysis, setAnalysis] = useState<TradeAnalyzeResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [tradeMessage, setTradeMessage] = useState("");
  const [tradeActionError, setTradeActionError] = useState<string | null>(null);
  const targetTeamIdParam = searchParams.get("teamId");
  const targetTeamId =
    targetTeamIdParam && /^\d+$/.test(targetTeamIdParam)
      ? Number(targetTeamIdParam)
      : null;

  useEffect(() => {
    if (!leagueId) return;
    if (activeLeagueId !== leagueId) {
      setActiveLeagueId(leagueId);
    }
  }, [activeLeagueId, leagueId, setActiveLeagueId]);

  useEffect(() => {
    if (!opponentTeams.length) {
      setOpponentTeamId(null);
      return;
    }
    setOpponentTeamId((current) => {
      if (current && opponentTeams.some((team) => team.id === current)) return current;
      return opponentTeams[0].id;
    });
  }, [opponentTeams]);

  useEffect(() => {
    if (!targetTeamId || targetTeamId === ownedTeamId) return;
    if (!opponentTeams.some((team) => team.id === targetTeamId)) return;
    setOpponentTeamId(targetTeamId);
  }, [opponentTeams, ownedTeamId, targetTeamId]);

  const {
    data: myRosterPayload,
    isLoading: myRosterLoading,
    isError: myRosterError,
  } = useTeamRoster(ownedTeamId ?? undefined, Boolean(ownedTeamId));

  const {
    data: theirRosterPayload,
    isLoading: theirRosterLoading,
    isError: theirRosterError,
  } = useTeamRoster(opponentTeamId ?? undefined, Boolean(opponentTeamId));

  const myRows = useMemo(() => toTradeRows(myRosterPayload?.data), [myRosterPayload?.data]);
  const theirRows = useMemo(() => {
    const directRows = toTradeRows(theirRosterPayload?.data);
    const fallbackRows = fallbackRowsByTeam.get(opponentTeamId ?? -1) ?? [];
    return directRows.length ? mergeProjectedValues(directRows, fallbackRows) : fallbackRows;
  }, [fallbackRowsByTeam, opponentTeamId, theirRosterPayload?.data]);
  const resolvedMyRows = useMemo(() => {
    const fallbackRows = fallbackRowsByTeam.get(ownedTeamId ?? -1) ?? [];
    if (myRows.length) return mergeProjectedValues(myRows, fallbackRows);
    return fallbackRows;
  }, [fallbackRowsByTeam, myRows, ownedTeamId]);
  const giveSet = useMemo(() => new Set(giveIds), [giveIds]);
  const receiveSet = useMemo(() => new Set(receiveIds), [receiveIds]);
  const selectedGiveRows = useMemo(
    () => resolvedMyRows.filter((row) => giveSet.has(row.playerId)),
    [giveSet, resolvedMyRows]
  );
  const selectedReceiveRows = useMemo(
    () => theirRows.filter((row) => receiveSet.has(row.playerId)),
    [receiveSet, theirRows]
  );
  const liveGiveValue = useMemo(
    () => selectedGiveRows.reduce((sum, row) => sum + (row.projectedPoints ?? 0), 0),
    [selectedGiveRows]
  );
  const liveReceiveValue = useMemo(
    () => selectedReceiveRows.reduce((sum, row) => sum + (row.projectedPoints ?? 0), 0),
    [selectedReceiveRows]
  );
  const liveDelta = liveReceiveValue - liveGiveValue;
  const partnerPlayerResults = useMemo(() => {
    const query = playerSearch.trim().toLowerCase();
    if (query.length < 2) return [];
    return allLeagueRosterRows
      .filter((row) => row.teamId !== ownedTeamId)
      .filter((row) =>
        [row.name, row.school, row.position, row.teamName ?? ""].some((value) =>
          value.toLowerCase().includes(query)
        )
      )
      .slice(0, 8);
  }, [allLeagueRosterRows, ownedTeamId, playerSearch]);

  useEffect(() => {
    const parsedPlayerId =
      playerIdParam && /^\d+$/.test(playerIdParam) ? Number(playerIdParam) : null;
    if (!parsedPlayerId) return;
    if (targetTeamId && targetTeamId === ownedTeamId && resolvedMyRows.some((row) => row.playerId === parsedPlayerId)) {
      setGiveIds((current) =>
        current.includes(parsedPlayerId) ? current : [...current, parsedPlayerId]
      );
      return;
    }
    if (theirRows.some((row) => row.playerId === parsedPlayerId)) {
      setReceiveIds((current) =>
        current.includes(parsedPlayerId) ? current : [...current, parsedPlayerId]
      );
      return;
    }
    if (resolvedMyRows.some((row) => row.playerId === parsedPlayerId)) {
      setGiveIds((current) =>
        current.includes(parsedPlayerId) ? current : [...current, parsedPlayerId]
      );
    }
  }, [resolvedMyRows, ownedTeamId, playerIdParam, targetTeamId, theirRows]);

  useEffect(() => {
    setAnalysis(null);
    setAnalysisError(null);
  }, [giveIds, receiveIds, opponentTeamId, leagueId]);

  const opponentTeam = teams.find((team) => team.id === opponentTeamId) ?? null;
  const ownedTeam = teams.find((team) => team.id === ownedTeamId) ?? null;
  const userMembership = settingsView?.members.find((member) => member.user_id === user?.id) ?? null;
  const isCommissioner = Boolean(
    league?.commissioner_user_id === user?.id || userMembership?.role === "commissioner"
  );
  const knownRowsByPlayerId = useMemo(() => {
    const rows = [...allLeagueRosterRows, ...resolvedMyRows, ...theirRows];
    return new Map(rows.map((row) => [row.playerId, row]));
  }, [allLeagueRosterRows, resolvedMyRows, theirRows]);

  const tradeOffersQuery = useQuery({
    queryKey: ["league", leagueId, "trades"],
    enabled: Boolean(leagueId),
    staleTime: 15_000,
    queryFn: () => apiGet<TradeOfferListResponse>(`/leagues/${leagueId}/trades`),
  });

  const invalidateTradeState = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "trades"] }),
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "settings-view"] }),
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] }),
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] }),
      queryClient.invalidateQueries({ queryKey: ["team", ownedTeamId, "roster"] }),
      queryClient.invalidateQueries({ queryKey: ["team", opponentTeamId, "roster"] }),
    ]);
  };

  const createTradeMutation = useMutation({
    mutationFn: (payload: TradeOfferCreatePayload) =>
      apiPost<TradeOffer>(`/leagues/${leagueId}/trades`, payload),
    onSuccess: async () => {
      setTradeMessage("");
      setGiveIds([]);
      setReceiveIds([]);
      setTradeActionError(null);
      await invalidateTradeState();
    },
  });

  const tradeActionMutation = useMutation({
    mutationFn: ({ tradeId, action }: { tradeId: number; action: "accept" | "reject" | "cancel" | "approve" | "veto" }) => {
      const path =
        action === "approve"
          ? `/trades/${tradeId}/commissioner/approve`
          : action === "veto"
          ? `/trades/${tradeId}/commissioner/veto`
          : `/trades/${tradeId}/${action}`;
      return apiPost<TradeOffer>(path, {});
    },
    onSuccess: async () => {
      setTradeActionError(null);
      await invalidateTradeState();
    },
  });

  const selectOpponentTeam = (teamId: number) => {
    setOpponentTeamId(teamId);
    setReceiveIds([]);
    setPlayerSearch("");
  };

  const selectTradeTargetPlayer = (row: TradeRow) => {
    setOpponentTeamId(row.teamId);
    setReceiveIds((current) => (current.includes(row.playerId) ? current : [...current, row.playerId]));
    setPlayerSearch("");
  };

  const toggleGive = (playerId: number) => {
    setGiveIds((current) =>
      current.includes(playerId)
        ? current.filter((id) => id !== playerId)
        : [...current, playerId]
    );
  };

  const toggleReceive = (playerId: number) => {
    setReceiveIds((current) =>
      current.includes(playerId)
        ? current.filter((id) => id !== playerId)
        : [...current, playerId]
    );
  };

  const handleAnalyze = async () => {
    if (!league || !workspace || !giveIds.length || !receiveIds.length) {
      return;
    }
    const payload: TradeAnalyzePayload = {
      receive_ids: receiveIds,
      give_ids: giveIds,
      season: league.season_year,
      week: Number(workspace.matchup_summary?.week ?? 1),
      league_size: league.max_teams,
      roster_slots: toTradeRosterSlots(league.settings?.roster_slots_json),
    };
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await apiPost<TradeAnalyzeResult>("/trade/analyze", payload);
      setAnalysis(result);
    } catch (error) {
      setAnalysis(null);
      setAnalysisError(error instanceof Error ? error.message : "Unable to analyze trade.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSendTrade = async () => {
    setTradeActionError(null);
    try {
      const payload = buildTradeOfferPayload({
        ownedTeamId,
        opponentTeamId,
        giveIds,
        receiveIds,
        message: tradeMessage,
      });
      await createTradeMutation.mutateAsync(payload);
    } catch (error) {
      setTradeActionError(error instanceof Error ? error.message : "Unable to send trade offer.");
    }
  };

  const handleTradeAction = async (
    tradeId: number,
    action: "accept" | "reject" | "cancel" | "approve" | "veto"
  ) => {
    setTradeActionError(null);
    try {
      await tradeActionMutation.mutateAsync({ tradeId, action });
    } catch (error) {
      setTradeActionError(error instanceof Error ? error.message : "Unable to update trade offer.");
    }
  };

  const teamName = (teamId: number) => teams.find((team) => team.id === teamId)?.name ?? `Team #${teamId}`;
  const tradePlayerName = (playerId: number | null) =>
    playerId ? knownRowsByPlayerId.get(playerId)?.name ?? `Player #${playerId}` : "Draft pick";
  const tradeItemsForTeam = (offer: TradeOffer, teamId: number) =>
    offer.items.filter((item) => item.team_id === teamId);
  const tradeIsOpen = (offer: TradeOffer) =>
    ["proposed", "commissioner_review"].includes(offer.status.toLowerCase());
  const tradeOffers = tradeOffersQuery.data?.data ?? [];
  const sendTradeDisabled =
    createTradeMutation.isPending ||
    !canSubmitTradeOffer(ownedTeamId, opponentTeamId, giveIds, receiveIds);

  if (!leagueId) {
    return (
      <div className="mx-auto max-w-4xl py-12">
        <Card className="rounded-[2rem] border border-white/10 bg-card/40">
          <CardContent className="space-y-4 p-10 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.25em] text-muted-foreground/70">
              No active league selected.
            </p>
            <Button
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Open Leagues
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-16 pt-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
            Trade Analyzer
          </p>
          <h1 className="text-6xl font-black italic uppercase tracking-tight text-foreground">
            Trade Builder
          </h1>
          <p className="text-sm text-muted-foreground">
            Select players from both rosters and compare trade value.
          </p>
        </div>
        <Button
          asChild
          variant="outline"
          className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
        >
          <Link to={`/league/${leagueId}`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to League
          </Link>
        </Button>
      </div>

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardContent className="grid gap-4 p-6 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Your Team
            </p>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-black uppercase tracking-[0.14em] text-foreground">
              {ownedTeam?.name ?? (ownedTeamId ? "Your Team" : "No team found for this league")}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Trade Partner
            </p>
            <Select
              value={opponentTeamId ? String(opponentTeamId) : ""}
              onValueChange={(value) => selectOpponentTeam(Number(value))}
            >
              <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.16em]">
                <SelectValue placeholder="Select team" />
              </SelectTrigger>
              <SelectContent>
                {opponentTeams.map((team: Team) => (
                  <SelectItem key={team.id} value={String(team.id)}>
                    {team.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 md:col-span-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Trade for specific player
            </p>
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-200/50" />
              <input
                value={playerSearch}
                onChange={(event) => setPlayerSearch(event.target.value)}
                placeholder="Search league rosters by player, school, position, or manager..."
                className="h-12 w-full rounded-xl border border-white/10 bg-white/[0.03] pl-11 pr-4 text-sm font-bold text-foreground outline-none transition focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/15"
              />
              {partnerPlayerResults.length > 0 ? (
                <div className="absolute z-20 mt-2 max-h-80 w-full overflow-auto rounded-2xl border border-sky-300/20 bg-[#071120]/95 p-2 shadow-[0_22px_80px_rgba(56,189,248,0.18)] backdrop-blur-xl">
                  {partnerPlayerResults.map((row) => (
                    <button
                      key={`${row.teamId}-${row.rosterEntryId}`}
                      type="button"
                      onClick={() => selectTradeTargetPlayer(row)}
                      className="flex w-full items-center justify-between gap-4 rounded-xl px-3 py-3 text-left transition hover:bg-sky-300/10"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-black text-foreground">{row.name}</p>
                        <p className="truncate text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                          {row.school} • {row.teamName ?? teams.find((team) => team.id === row.teamId)?.name ?? "Manager"}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded-xl border px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em]",
                          POS_STYLES[row.position] ?? POS_STYLES.QB
                        )}
                      >
                        {row.position}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <TradeList
          title="Players You Give"
          subtitle={myRosterLoading ? "Loading roster..." : "Select one or more players"}
          rows={resolvedMyRows}
          selectedIds={giveSet}
          onToggle={toggleGive}
        />
        <TradeList
          title={`Players You Receive${opponentTeam ? ` (${opponentTeam.name})` : ""}`}
          subtitle={theirRosterLoading ? "Loading roster..." : "Select one or more players"}
          rows={theirRows}
          selectedIds={receiveSet}
          onToggle={toggleReceive}
        />
      </div>

      {(myRosterError || theirRosterError) && (
        <Card className="rounded-[2rem] border border-red-400/30 bg-red-500/10">
          <CardContent className="flex items-center gap-3 p-6 text-sm text-red-200">
            <ShieldAlert className="h-5 w-5" />
            Unable to load one or more rosters. Please retry or switch leagues.
          </CardContent>
        </Card>
      )}

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader className="flex flex-row items-center justify-between border-b border-white/10">
          <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.2em] text-primary">
            <ArrowRightLeft className="h-4 w-4" />
            Trade Analysis
          </CardTitle>
          <Button
            className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
            disabled={isAnalyzing || !giveIds.length || !receiveIds.length || !league || !workspace}
            onClick={handleAnalyze}
          >
            {isAnalyzing ? "Analyzing..." : "Analyze Trade"}
            {!isAnalyzing && <ChevronRight className="ml-2 h-4 w-4" />}
          </Button>
        </CardHeader>
        <CardContent className="space-y-6 p-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Giving
              </p>
              <p className="mt-2 text-2xl font-black italic text-foreground">
                {liveGiveValue.toFixed(1)}
              </p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                {giveIds.length} selected
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Receiving
              </p>
              <p className="mt-2 text-2xl font-black italic text-foreground">
                {liveReceiveValue.toFixed(1)}
              </p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                {receiveIds.length} selected
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Live Delta
              </p>
              <p
                className={cn(
                  "mt-2 text-2xl font-black italic",
                  liveDelta > 0 ? "text-emerald-300" : liveDelta < 0 ? "text-red-300" : "text-foreground"
                )}
              >
                {liveDelta >= 0 ? "+" : ""}
                {liveDelta.toFixed(1)}
              </p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                Projection-based
              </p>
            </div>
          </div>

          {analysisError && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {analysisError}
            </p>
          )}

          {analysis ? (
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Give Value
                </p>
                <p className="mt-2 text-xl font-black text-foreground">{analysis.give_value.toFixed(2)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Receive Value
                </p>
                <p className="mt-2 text-xl font-black text-foreground">
                  {analysis.receive_value.toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Delta
                </p>
                <p
                  className={cn(
                    "mt-2 text-xl font-black",
                    analysis.delta >= 0 ? "text-emerald-300" : "text-red-300"
                  )}
                >
                  {analysis.delta >= 0 ? "+" : ""}
                  {analysis.delta.toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Verdict
                </p>
                <p className="mt-2 text-xl font-black text-primary">{analysis.verdict}</p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Select players from both sides, then run analysis to see value differential.
              </p>
            </div>
          )}
          <div className="flex flex-col gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-bold text-muted-foreground">
              Trade offers are submitted to the backend proposal workflow and stay auditable through final processing.
            </p>
            <Button
              className="h-11 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
              disabled={sendTradeDisabled}
              onClick={() => void handleSendTrade()}
            >
              {createTradeMutation.isPending ? "Sending..." : "Send Trade Offer"}
            </Button>
          </div>
          <div className="space-y-2 border-t border-white/10 pt-5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Message to manager
            </p>
            <textarea
              value={tradeMessage}
              onChange={(event) => setTradeMessage(event.target.value)}
              maxLength={500}
              placeholder="Optional note explaining this trade."
              className="min-h-24 w-full rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-bold text-foreground outline-none transition placeholder:text-muted-foreground/50 focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/15"
            />
          </div>
          {tradeActionError && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {tradeActionError}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.2em] text-primary">
            <Clock3 className="h-4 w-4" />
            Trade Offers
          </CardTitle>
          <p className="text-xs font-bold text-muted-foreground">
            Pending, accepted, rejected, cancelled, vetoed, and processed trade records for this league.
          </p>
        </CardHeader>
        <CardContent className="space-y-4 p-6">
          {tradeOffersQuery.isLoading ? (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Loading trade offers...
            </p>
          ) : tradeOffers.length === 0 ? (
            <p className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              No trade offers have been submitted in this league yet.
            </p>
          ) : (
            tradeOffers.map((offer) => {
              const proposingItems = tradeItemsForTeam(offer, offer.proposing_team_id);
              const receivingItems = tradeItemsForTeam(offer, offer.receiving_team_id);
              const canAccept = offer.status === "proposed" && offer.receiving_team_id === ownedTeamId;
              const canReject = tradeIsOpen(offer) && offer.receiving_team_id === ownedTeamId;
              const canCancel = tradeIsOpen(offer) && offer.proposing_team_id === ownedTeamId;
              const canReview = isCommissioner && offer.status === "commissioner_review";
              return (
                <div key={offer.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                        {tradeStatusLabel(offer.status)}
                      </p>
                      <p className="mt-2 text-lg font-black text-foreground">
                        {teamName(offer.proposing_team_id)} ↔ {teamName(offer.receiving_team_id)}
                      </p>
                      <p className="mt-1 text-xs font-bold text-muted-foreground">
                        Created {new Date(offer.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {canAccept && (
                        <Button size="sm" className="rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void handleTradeAction(offer.id, "accept")} disabled={tradeActionMutation.isPending}>
                          <Check className="mr-2 h-3.5 w-3.5" />
                          Accept
                        </Button>
                      )}
                      {canReject && (
                        <Button size="sm" variant="outline" className="rounded-xl border-red-300/30 bg-red-500/10 text-[10px] font-black uppercase tracking-[0.16em] text-red-200" onClick={() => void handleTradeAction(offer.id, "reject")} disabled={tradeActionMutation.isPending}>
                          <X className="mr-2 h-3.5 w-3.5" />
                          Reject
                        </Button>
                      )}
                      {canCancel && (
                        <Button size="sm" variant="outline" className="rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void handleTradeAction(offer.id, "cancel")} disabled={tradeActionMutation.isPending}>
                          Cancel
                        </Button>
                      )}
                      {canReview && (
                        <>
                          <Button size="sm" className="rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void handleTradeAction(offer.id, "approve")} disabled={tradeActionMutation.isPending}>
                            Approve
                          </Button>
                          <Button size="sm" variant="outline" className="rounded-xl border-red-300/30 bg-red-500/10 text-[10px] font-black uppercase tracking-[0.16em] text-red-200" onClick={() => void handleTradeAction(offer.id, "veto")} disabled={tradeActionMutation.isPending}>
                            Veto
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
                        {teamName(offer.proposing_team_id)} sends
                      </p>
                      <p className="mt-2 text-sm font-black text-foreground">
                        {proposingItems.map((item) => tradePlayerName(item.player_id)).join(", ")}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
                        {teamName(offer.receiving_team_id)} sends
                      </p>
                      <p className="mt-2 text-sm font-black text-foreground">
                        {receivingItems.map((item) => tradePlayerName(item.player_id)).join(", ")}
                      </p>
                    </div>
                  </div>
                  {offer.message && (
                    <p className="mt-4 rounded-xl border border-white/10 bg-black/10 p-3 text-sm font-semibold text-muted-foreground">
                      {offer.message}
                    </p>
                  )}
                  {offer.reviews.length > 0 && (
                    <div className="mt-4 border-t border-white/10 pt-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
                        Audit Trail
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {offer.reviews.map((review) => (
                          <span key={review.id} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                            {review.action} · {new Date(review.created_at).toLocaleDateString()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card className="rounded-[2rem] border border-emerald-400/20 bg-emerald-500/10">
        <CardContent className="flex items-center gap-3 p-5 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-100">
          <Users className="h-4 w-4" />
          Trade value is calculated from your league rosters and weekly projections.
        </CardContent>
      </Card>
    </div>
  );
}
