import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRightLeft,
  Check,
  ChevronRight,
  Search,
  ShieldAlert,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { resolveTradeOfferReturnPath } from "@/lib/trade-links";
import { cn } from "@/lib/utils";
import type { LeagueRosterPlayer } from "@/types/league";
import type { RosterEntry } from "@/types/roster";
import type { Team } from "@/types/team";

const OFFENSE_POSITIONS = new Set(["QB", "RB", "WR", "TE", "K"]);

const createClientTradeRequestId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `trade-${Date.now()}-${Math.random().toString(36).slice(2)}`;

type TradeAnalyzePayload = {
  receive_ids: number[];
  give_ids: number[];
  season: number;
  week: number;
  league_id?: number;
  league_size: number;
  roster_slots: Record<string, number>;
};

type TradeAnalyzeResult = {
  receive_value: number | null;
  give_value: number | null;
  delta: number | null;
  verdict: string;
  unavailable_player_ids: number[];
};

type TradeOfferItem = {
  id: number;
  trade_offer_id: number;
  team_id: number;
  player_id: number | null;
  draft_pick_id: number | null;
  item_type: string;
  player_name?: string | null;
  player_position?: string | null;
  player_school?: string | null;
};

type TradeOffer = {
  id: number;
  league_id: number;
  proposing_team_id: number;
  receiving_team_id: number;
  created_by_user_id: number | null;
  status: string;
  message: string | null;
  accepted_at: string | null;
  process_after: string | null;
  processed_at: string | null;
  failure_reason: string | null;
  countered_from_trade_id: number | null;
  items: TradeOfferItem[];
};

type TradeOfferListResponse = {
  data: TradeOffer[];
  total: number;
};

/**
 * `apiGet` is intentionally generic, so it cannot protect a route component
 * from an old proxy/cache returning the collection envelope for a detail URL.
 * Keep the deep-link modal open and show its safe unavailable state instead of
 * dereferencing `items` and taking down the route.
 */
const isTradeOfferPayload = (value: unknown): value is TradeOffer => {
  if (!value || typeof value !== "object") return false;
  const offer = value as Record<string, unknown>;
  return (
    typeof offer.id === "number" &&
    typeof offer.league_id === "number" &&
    typeof offer.proposing_team_id === "number" &&
    typeof offer.receiving_team_id === "number" &&
    typeof offer.status === "string" &&
    Array.isArray(offer.items)
  );
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

const POS_STYLES: Record<string, string> = {
  QB: "bg-blue-500/20 border-blue-400/30 text-blue-300",
  RB: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300",
  WR: "bg-violet-500/20 border-violet-400/30 text-violet-300",
  TE: "bg-amber-500/20 border-amber-400/30 text-amber-300",
  K: "bg-cyan-500/20 border-cyan-400/30 text-cyan-300",
};

export const formatTradeError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError && error.message) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

export const toTradeRows = (entries: RosterEntry[] | undefined): TradeRow[] => {
  if (!entries?.length) return [];
  return entries
    .flatMap((entry) => {
      // Empty roster placeholders intentionally have no player. They must stay
      // visible in lineup views, but they are never valid trade assets.
      const player = entry.player;
      const position = player?.position?.toUpperCase() ?? "";
      if (!player || !OFFENSE_POSITIONS.has(position)) return [];
      return [
        {
          rosterEntryId: entry.id,
          playerId: player.id,
          teamId: entry.team_id,
          name: player.name,
          position,
          school: player.school ?? "",
          slot: (entry.slot || "BENCH").toUpperCase(),
        },
      ];
    })
    .sort((a, b) => {
      const starterA = a.slot !== "BENCH" ? 0 : 1;
      const starterB = b.slot !== "BENCH" ? 0 : 1;
      if (starterA !== starterB) return starterA - starterB;
      return a.name.localeCompare(b.name);
    });
};

const toTradeRowsFromLeagueRoster = (
  entries: LeagueRosterPlayer[] | undefined,
): TradeRow[] => {
  if (!entries?.length) return [];
  return entries
    .filter((entry) => {
      const position = (
        entry.player_position ??
        entry.position ??
        ""
      ).toUpperCase();
      return (
        entry.player_id !== null &&
        entry.player_id !== undefined &&
        !entry.is_placeholder &&
        OFFENSE_POSITIONS.has(position)
      );
    })
    .map((entry) => ({
      rosterEntryId: entry.id,
      playerId: entry.player_id as number,
      teamId: entry.fantasy_team_id ?? entry.team_id ?? 0,
      teamName: entry.fantasy_team_name,
      name: entry.player_name,
      position: (entry.player_position ?? entry.position ?? "").toUpperCase(),
      school: entry.player_school ?? entry.school ?? "",
      slot: (entry.roster_slot ?? entry.slot ?? "BENCH").toUpperCase(),
      projectedPoints:
        entry.projected_points ?? entry.weekly_projected_fantasy_points ?? 0,
    }))
    .filter((entry) => entry.teamId > 0)
    .sort((a, b) => {
      const starterA = a.slot !== "BENCH" ? 0 : 1;
      const starterB = b.slot !== "BENCH" ? 0 : 1;
      if (starterA !== starterB) return starterA - starterB;
      return a.name.localeCompare(b.name);
    });
};

const mergeProjectedValues = (
  rows: TradeRow[],
  fallbackRows: TradeRow[],
): TradeRow[] => {
  if (!rows.length || !fallbackRows.length) return rows;
  const fallbackByTeamPlayer = new Map(
    fallbackRows.map((row) => [`${row.teamId}:${row.playerId}`, row]),
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

export const tradeSelectionSignature = (
  leagueId: number | undefined,
  opponentTeamId: number | null,
  giveIds: number[],
  receiveIds: number[],
) =>
  JSON.stringify({
    leagueId: leagueId ?? null,
    opponentTeamId,
    giveIds: [...giveIds].sort((a, b) => a - b),
    receiveIds: [...receiveIds].sort((a, b) => a - b),
  });

export const canSendTradeOffer = (
  analysis: TradeAnalyzeResult | null,
  analysisSignature: string | null,
  currentSignature: string,
  isSending: boolean,
) =>
  Boolean(
    analysis &&
    analysis.receive_value !== null &&
    analysis.give_value !== null &&
    analysis.delta !== null &&
    analysisSignature === currentSignature &&
    !isSending,
  );

const formatTradeStatus = (status: string) =>
  status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const toTradeRosterSlots = (
  slots: Record<string, number> | undefined,
): Record<string, number> => {
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
  direction,
  rows,
  selectedIds,
  onToggle,
}: {
  title: string;
  subtitle: string;
  direction: "give" | "receive";
  rows: TradeRow[];
  selectedIds: Set<number>;
  onToggle: (playerId: number) => void;
}) => {
  const isGiving = direction === "give";
  const selectionClasses = isGiving
    ? "border-rose-300/40 bg-rose-500/10 shadow-[0_12px_35px_rgba(244,63,94,0.08)]"
    : "border-emerald-300/40 bg-emerald-500/10 shadow-[0_12px_35px_rgba(16,185,129,0.08)]";
  const accentClasses = isGiving
    ? "border-rose-300/25 bg-rose-500/10 text-rose-100"
    : "border-emerald-300/25 bg-emerald-500/10 text-emerald-100";

  if (!rows.length) {
    return (
      <Card className="overflow-hidden rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10 bg-white/[0.02]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="min-w-0">
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-foreground">
                {title}
              </CardTitle>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
                {subtitle}
              </p>
            </div>
            <span
              className={cn(
                "w-fit shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-[9px] font-black uppercase tracking-[0.14em]",
                accentClasses,
              )}
            >
              {isGiving ? "You send" : "You receive"}
            </span>
          </div>
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
    <Card className="overflow-hidden rounded-[2rem] border border-white/10 bg-card/40">
      <CardHeader className="border-b border-white/10 bg-white/[0.02]">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="min-w-0">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-foreground">
              {title}
            </CardTitle>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
              {subtitle}
            </p>
          </div>
          <span
            className={cn(
              "w-fit shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-[9px] font-black uppercase tracking-[0.14em]",
              accentClasses,
            )}
          >
            {selectedIds.size} chosen
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4">
        {rows.map((row) => {
          const selected = selectedIds.has(row.playerId);
          return (
            <button
              key={row.rosterEntryId}
              type="button"
              onClick={() => onToggle(row.playerId)}
              aria-pressed={selected}
              className={cn(
                "group w-full rounded-2xl border px-4 py-3 text-left transition-all duration-200",
                selected
                  ? selectionClasses
                  : "border-white/10 bg-white/[0.03] hover:-translate-y-0.5 hover:border-white/25 hover:bg-white/[0.055]",
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
                <div className="flex shrink-0 items-center gap-2">
                  {selected ? (
                    <span
                      className={cn(
                        "grid h-7 w-7 place-items-center rounded-full border",
                        accentClasses,
                      )}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </span>
                  ) : null}
                  <span
                    className={cn(
                      "rounded-xl border px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em]",
                      POS_STYLES[row.position] ?? POS_STYLES.QB,
                    )}
                  >
                    {row.position}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default function Trade() {
  const {
    leagueId: leagueIdParam,
    playerId: playerIdParam,
    tradeId: tradeIdParam,
  } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { data: leagues = [] } = useLeagues(50, true);
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();

  const parsedLeagueId =
    leagueIdParam && /^\d+$/.test(leagueIdParam)
      ? Number(leagueIdParam)
      : undefined;
  const requestedTradeId =
    tradeIdParam && /^\d+$/.test(tradeIdParam)
      ? Number(tradeIdParam)
      : undefined;
  const isTradeOfferRoute = tradeIdParam !== undefined;
  const fallbackLeagueId = activeLeagueId ?? leagues[0]?.id;
  const leagueId = parsedLeagueId ?? fallbackLeagueId;

  const { data: league } = useLeagueDetail(leagueId, Boolean(leagueId));
  const { data: workspace } = useLeagueWorkspace(leagueId, Boolean(leagueId));
  const { data: teamsPayload } = useLeagueTeams(leagueId, Boolean(leagueId));
  const { data: settingsView } = useLeagueSettingsTab(
    leagueId,
    Boolean(leagueId),
  );

  const teams = teamsPayload?.data ?? [];
  const ownedTeamId =
    workspace?.owned_team?.id ??
    teams.find((team) => team.owner_user_id && team.owner_user_id === user?.id)
      ?.id ??
    null;
  const opponentTeams = useMemo(
    () => teams.filter((team) => team.id !== ownedTeamId),
    [ownedTeamId, teams],
  );
  const allLeagueRosterRows = useMemo(
    () => toTradeRowsFromLeagueRoster(settingsView?.rosters),
    [settingsView?.rosters],
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
  const [analysisSignature, setAnalysisSignature] = useState<string | null>(
    null,
  );
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isAnalysisReviewOpen, setIsAnalysisReviewOpen] = useState(false);
  const [tradeMessage, setTradeMessage] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [counteringOfferId, setCounteringOfferId] = useState<number | null>(
    null,
  );
  const pendingTradeRequest = useRef<{ signature: string; id: string } | null>(
    null,
  );
  const targetTeamIdParam = searchParams.get("teamId");
  const targetTeamId =
    targetTeamIdParam && /^\d+$/.test(targetTeamIdParam)
      ? Number(targetTeamIdParam)
      : null;
  const focusedOfferReturnPath = resolveTradeOfferReturnPath(
    searchParams.get("returnTo"),
  );

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
      if (current && opponentTeams.some((team) => team.id === current))
        return current;
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

  const myRows = useMemo(
    () => toTradeRows(myRosterPayload?.data),
    [myRosterPayload?.data],
  );
  const theirRows = useMemo(() => {
    const directRows = toTradeRows(theirRosterPayload?.data);
    const fallbackRows = fallbackRowsByTeam.get(opponentTeamId ?? -1) ?? [];
    return directRows.length
      ? mergeProjectedValues(directRows, fallbackRows)
      : fallbackRows;
  }, [fallbackRowsByTeam, opponentTeamId, theirRosterPayload?.data]);
  const resolvedMyRows = useMemo(() => {
    const fallbackRows = fallbackRowsByTeam.get(ownedTeamId ?? -1) ?? [];
    if (myRows.length) return mergeProjectedValues(myRows, fallbackRows);
    return fallbackRows;
  }, [fallbackRowsByTeam, myRows, ownedTeamId]);
  const giveSet = useMemo(() => new Set(giveIds), [giveIds]);
  const receiveSet = useMemo(() => new Set(receiveIds), [receiveIds]);
  const currentTradeSignature = useMemo(
    () =>
      tradeSelectionSignature(leagueId, opponentTeamId, giveIds, receiveIds),
    [giveIds, leagueId, opponentTeamId, receiveIds],
  );
  const tradeSubmitSignature = useMemo(
    () =>
      JSON.stringify({
        selection: currentTradeSignature,
        counterTradeId: counteringOfferId,
        message: tradeMessage.trim(),
      }),
    [counteringOfferId, currentTradeSignature, tradeMessage],
  );
  const selectedGiveRows = useMemo(
    () => resolvedMyRows.filter((row) => giveSet.has(row.playerId)),
    [giveSet, resolvedMyRows],
  );
  const selectedReceiveRows = useMemo(
    () => theirRows.filter((row) => receiveSet.has(row.playerId)),
    [receiveSet, theirRows],
  );
  const liveGiveValue = useMemo(
    () =>
      selectedGiveRows.reduce(
        (sum, row) => sum + (row.projectedPoints ?? 0),
        0,
      ),
    [selectedGiveRows],
  );
  const liveReceiveValue = useMemo(
    () =>
      selectedReceiveRows.reduce(
        (sum, row) => sum + (row.projectedPoints ?? 0),
        0,
      ),
    [selectedReceiveRows],
  );
  const liveDelta = liveReceiveValue - liveGiveValue;
  const partnerPlayerResults = useMemo(() => {
    const query = playerSearch.trim().toLowerCase();
    if (query.length < 2) return [];
    return allLeagueRosterRows
      .filter((row) => row.teamId !== ownedTeamId)
      .filter((row) =>
        [row.name, row.school, row.position, row.teamName ?? ""].some((value) =>
          value.toLowerCase().includes(query),
        ),
      )
      .slice(0, 8);
  }, [allLeagueRosterRows, ownedTeamId, playerSearch]);

  useEffect(() => {
    const parsedPlayerId =
      playerIdParam && /^\d+$/.test(playerIdParam)
        ? Number(playerIdParam)
        : null;
    if (!parsedPlayerId) return;
    const leagueRosterTarget = allLeagueRosterRows.find(
      (row) => row.playerId === parsedPlayerId,
    );
    if (
      leagueRosterTarget &&
      leagueRosterTarget.teamId !== ownedTeamId &&
      opponentTeams.some((team) => team.id === leagueRosterTarget.teamId)
    ) {
      setOpponentTeamId(leagueRosterTarget.teamId);
      setReceiveIds((current) =>
        current.includes(parsedPlayerId)
          ? current
          : [...current, parsedPlayerId],
      );
      return;
    }
    if (
      targetTeamId &&
      targetTeamId === ownedTeamId &&
      resolvedMyRows.some((row) => row.playerId === parsedPlayerId)
    ) {
      setGiveIds((current) =>
        current.includes(parsedPlayerId)
          ? current
          : [...current, parsedPlayerId],
      );
      return;
    }
    if (theirRows.some((row) => row.playerId === parsedPlayerId)) {
      setReceiveIds((current) =>
        current.includes(parsedPlayerId)
          ? current
          : [...current, parsedPlayerId],
      );
      return;
    }
    if (resolvedMyRows.some((row) => row.playerId === parsedPlayerId)) {
      setGiveIds((current) =>
        current.includes(parsedPlayerId)
          ? current
          : [...current, parsedPlayerId],
      );
    }
  }, [
    allLeagueRosterRows,
    opponentTeams,
    resolvedMyRows,
    ownedTeamId,
    playerIdParam,
    targetTeamId,
    theirRows,
  ]);

  useEffect(() => {
    setAnalysis(null);
    setAnalysisSignature(null);
    setAnalysisError(null);
    setIsAnalysisReviewOpen(false);
    setSendError(null);
  }, [giveIds, receiveIds, opponentTeamId, leagueId]);

  const offersQuery = useQuery({
    queryKey: ["league", leagueId, "trade-offers"],
    enabled: Boolean(leagueId),
    queryFn: () =>
      apiGet<TradeOfferListResponse>(`/leagues/${leagueId}/trades`),
  });

  const focusedOfferQuery = useQuery({
    queryKey: ["league", leagueId, "trade-offer", requestedTradeId],
    enabled: Boolean(isTradeOfferRoute && leagueId && requestedTradeId),
    queryFn: () =>
      apiGet<TradeOffer>(`/leagues/${leagueId}/trades/${requestedTradeId}`),
  });

  const focusedOffer = isTradeOfferPayload(focusedOfferQuery.data)
    ? focusedOfferQuery.data
    : null;
  const focusedOfferUnavailable =
    focusedOfferQuery.isError ||
    !requestedTradeId ||
    Boolean(focusedOfferQuery.data && !focusedOffer);

  const closeFocusedOffer = () =>
    navigate(focusedOfferReturnPath, { replace: true });

  const createOfferMutation = useMutation({
    mutationFn: ({
      counterTradeId,
      clientRequestId,
    }: {
      counterTradeId: number | null;
      clientRequestId: string;
    }) =>
      apiPost<TradeOffer>(
        counterTradeId
          ? `/leagues/${leagueId}/trades/${counterTradeId}/counter`
          : `/leagues/${leagueId}/trades`,
        {
          proposing_team_id: ownedTeamId,
          receiving_team_id: opponentTeamId,
          give_items: selectedGiveRows.map((row) => ({
            team_id: row.teamId,
            player_id: row.playerId,
          })),
          receive_items: selectedReceiveRows.map((row) => ({
            team_id: row.teamId,
            player_id: row.playerId,
          })),
          message: tradeMessage.trim() || null,
          client_request_id: clientRequestId,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["league", leagueId, "trade-offers"],
      });
      queryClient.invalidateQueries({ queryKey: ["notifications", "alerts"] });
      setGiveIds([]);
      setReceiveIds([]);
      setTradeMessage("");
      setCounteringOfferId(null);
      pendingTradeRequest.current = null;
      setIsAnalysisReviewOpen(false);
      setSendError(null);
    },
    onError: (error) =>
      setSendError(formatTradeError(error, "Unable to send trade offer.")),
  });

  const tradeActionMutation = useMutation({
    mutationFn: ({
      tradeId,
      action,
    }: {
      tradeId: number;
      action:
        | "accept"
        | "reject"
        | "cancel"
        | "commissioner/approve"
        | "commissioner/veto";
    }) =>
      apiPost<TradeOffer>(
        `/leagues/${leagueId}/trades/${tradeId}/${action}`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["league", leagueId, "trade-offers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["league", leagueId, "workspace"],
      });
      queryClient.invalidateQueries({ queryKey: ["notifications", "alerts"] });
      setActionError(null);
    },
    onError: (error) =>
      setActionError(formatTradeError(error, "Unable to update trade offer.")),
  });

  const opponentTeam = teams.find((team) => team.id === opponentTeamId) ?? null;
  const ownedTeam = teams.find((team) => team.id === ownedTeamId) ?? null;

  const selectOpponentTeam = (teamId: number) => {
    setOpponentTeamId(teamId);
    setReceiveIds([]);
    setPlayerSearch("");
  };

  const selectTradeTargetPlayer = (row: TradeRow) => {
    setOpponentTeamId(row.teamId);
    setReceiveIds((current) =>
      current.includes(row.playerId) ? current : [...current, row.playerId],
    );
    setPlayerSearch("");
  };

  const toggleGive = (playerId: number) => {
    setGiveIds((current) =>
      current.includes(playerId)
        ? current.filter((id) => id !== playerId)
        : [...current, playerId],
    );
  };

  const toggleReceive = (playerId: number) => {
    setReceiveIds((current) =>
      current.includes(playerId)
        ? current.filter((id) => id !== playerId)
        : [...current, playerId],
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
      league_id: league.id,
      league_size: league.max_teams,
      roster_slots: toTradeRosterSlots(league.settings?.roster_slots_json),
    };
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await apiPost<TradeAnalyzeResult>(
        "/trade/analyze",
        payload,
      );
      setAnalysis(result);
      setAnalysisSignature(currentTradeSignature);
      setIsAnalysisReviewOpen(true);
    } catch (error) {
      setAnalysis(null);
      setAnalysisSignature(null);
      setAnalysisError(formatTradeError(error, "Unable to analyze trade."));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const analysisIsCurrent = Boolean(
    analysis && analysisSignature === currentTradeSignature,
  );
  const sendEnabled =
    canSendTradeOffer(
      analysis,
      analysisSignature,
      currentTradeSignature,
      createOfferMutation.isPending,
    ) &&
    Boolean(
      ownedTeamId &&
      opponentTeamId &&
      selectedGiveRows.length &&
      selectedReceiveRows.length,
    );

  const handleSendTrade = () => {
    if (!sendEnabled) {
      setSendError("Run a fresh trade analysis before sending this offer.");
      return;
    }
    setSendError(null);
    const request =
      pendingTradeRequest.current?.signature === tradeSubmitSignature
        ? pendingTradeRequest.current
        : { signature: tradeSubmitSignature, id: createClientTradeRequestId() };
    pendingTradeRequest.current = request;
    createOfferMutation.mutate({
      counterTradeId: counteringOfferId,
      clientRequestId: request.id,
    });
  };

  const beginCounterOffer = (offer: TradeOffer) => {
    const originalGiveIds = offer.items
      .filter(
        (item) =>
          item.team_id === offer.proposing_team_id && item.player_id !== null,
      )
      .map((item) => item.player_id as number);
    const originalReceiveIds = offer.items
      .filter(
        (item) =>
          item.team_id === offer.receiving_team_id && item.player_id !== null,
      )
      .map((item) => item.player_id as number);
    setOpponentTeamId(offer.proposing_team_id);
    setGiveIds(originalReceiveIds);
    setReceiveIds(originalGiveIds);
    setTradeMessage(`Counter to trade #${offer.id}`);
    setCounteringOfferId(offer.id);
    setSendError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

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
      <div className="relative overflow-hidden rounded-[2.25rem] border border-sky-300/20 bg-[radial-gradient(circle_at_88%_8%,rgba(56,189,248,0.18),transparent_30%),radial-gradient(circle_at_10%_100%,rgba(168,85,247,0.15),transparent_34%),rgba(9,20,37,0.9)] px-6 py-7 shadow-[0_24px_75px_rgba(14,116,144,0.16)] sm:px-8">
        <div className="absolute right-6 top-5 hidden h-28 w-28 rounded-full border border-sky-200/10 bg-sky-300/[0.035] sm:block" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="flex items-center gap-3">
              <span className="rounded-full border border-sky-200/25 bg-sky-300/10 px-3 py-1 text-[9px] font-black uppercase tracking-[0.22em] text-sky-100">
                Trade desk
              </span>
              <span className="text-[9px] font-black uppercase tracking-[0.22em] text-slate-400">
                Build · Analyze · Send
              </span>
            </div>
            <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground sm:text-6xl">
              Trade Builder
            </h1>
            <p className="max-w-xl text-sm font-semibold leading-6 text-slate-300/85">
              {counteringOfferId
                ? `Countering trade #${counteringOfferId}. Update either side, then run a fresh analysis.`
                : "Build a clear offer, compare the current projection edge, and send only after a fresh review."}
            </p>
          </div>
          <Button
            asChild
            variant="outline"
            className="h-11 shrink-0 rounded-2xl border-white/15 bg-white/[0.045] text-[10px] font-black uppercase tracking-[0.2em] hover:bg-white/10"
          >
            <Link to={`/league/${leagueId}`}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to League
            </Link>
          </Button>
        </div>
      </div>

      <Card className="overflow-visible rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10 bg-white/[0.02]">
          <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.2em] text-foreground">
            <span className="grid h-7 w-7 place-items-center rounded-full border border-sky-300/30 bg-sky-300/10 text-[10px] text-sky-100">
              1
            </span>
            Choose the matchup
          </CardTitle>
          <p className="pt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
            Pick a manager, then add assets from each roster.
          </p>
        </CardHeader>
        <CardContent className="grid gap-4 p-6 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Your Team
            </p>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-black uppercase tracking-[0.14em] text-foreground">
              {ownedTeam?.name ??
                (ownedTeamId ? "Your Team" : "No team found for this league")}
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
                        <p className="truncate text-sm font-black text-foreground">
                          {row.name}
                        </p>
                        <p className="truncate text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                          {row.school} •{" "}
                          {row.teamName ??
                            teams.find((team) => team.id === row.teamId)
                              ?.name ??
                            "Manager"}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded-xl border px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em]",
                          POS_STYLES[row.position] ?? POS_STYLES.QB,
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

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_4.5rem_minmax(0,1fr)] xl:items-stretch">
        <TradeList
          title="Players You Give"
          subtitle={
            myRosterLoading ? "Loading roster..." : "Select one or more players"
          }
          direction="give"
          rows={resolvedMyRows}
          selectedIds={giveSet}
          onToggle={toggleGive}
        />
        <div className="hidden xl:flex xl:items-center xl:justify-center">
          <div className="grid h-14 w-14 place-items-center rounded-full border border-sky-300/25 bg-sky-300/10 text-sky-100 shadow-[0_12px_35px_rgba(56,189,248,0.15)]">
            <ArrowRightLeft className="h-5 w-5" />
          </div>
        </div>
        <TradeList
          title={`Players You Receive${opponentTeam ? ` (${opponentTeam.name})` : ""}`}
          subtitle={
            theirRosterLoading
              ? "Loading roster..."
              : "Select one or more players"
          }
          direction="receive"
          rows={theirRows}
          selectedIds={receiveSet}
          onToggle={toggleReceive}
        />
      </div>

      {(myRosterError || theirRosterError) && (
        <Card className="rounded-[2rem] border border-red-400/30 bg-red-500/10">
          <CardContent className="flex items-center gap-3 p-6 text-sm text-red-200">
            <ShieldAlert className="h-5 w-5" />
            {formatTradeError(
              myRosterError || theirRosterError,
              "Unable to load one or more rosters. Please retry or switch leagues.",
            )}
          </CardContent>
        </Card>
      )}

      <Card className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(14,31,54,0.92),rgba(8,18,35,0.92))] shadow-[0_22px_70px_rgba(8,47,73,0.14)]">
        <CardHeader className="flex flex-row items-center justify-between border-b border-white/10 bg-white/[0.02]">
          <div>
            <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.2em] text-foreground">
              <span className="grid h-7 w-7 place-items-center rounded-full border border-sky-300/30 bg-sky-300/10 text-sky-100">
                2
              </span>
              Trade snapshot
            </CardTitle>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
              Projection context before you send
            </p>
          </div>
          <Button
            className="h-10 rounded-xl bg-gradient-to-r from-sky-300 to-blue-500 px-4 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950 shadow-[0_10px_30px_rgba(59,130,246,0.25)] hover:from-sky-200 hover:to-blue-400"
            disabled={
              isAnalyzing ||
              !giveIds.length ||
              !receiveIds.length ||
              !league ||
              !workspace
            }
            onClick={() =>
              analysisIsCurrent
                ? setIsAnalysisReviewOpen(true)
                : handleAnalyze()
            }
          >
            {isAnalyzing
              ? "Analyzing..."
              : analysisIsCurrent
                ? "Review Analysis"
                : "Analyze Trade"}
            {!isAnalyzing && <ChevronRight className="ml-2 h-4 w-4" />}
          </Button>
        </CardHeader>
        <CardContent className="space-y-6 p-6">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-stretch">
            <div className="rounded-2xl border border-rose-300/20 bg-rose-500/[0.075] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-100">
                You send
              </p>
              <p className="mt-3 text-4xl font-black italic tabular-nums text-foreground">
                {liveGiveValue.toFixed(1)}
              </p>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.16em] text-rose-100/65">
                {giveIds.length} asset{giveIds.length === 1 ? "" : "s"} selected
              </p>
            </div>
            <div className="hidden lg:flex lg:items-center">
              <div className="grid h-12 w-12 place-items-center rounded-full border border-sky-300/20 bg-sky-300/10 text-sky-100">
                <ArrowRightLeft className="h-4 w-4" />
              </div>
            </div>
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-500/[0.075] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100">
                You receive
              </p>
              <p className="mt-3 text-4xl font-black italic tabular-nums text-foreground">
                {liveReceiveValue.toFixed(1)}
              </p>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.16em] text-emerald-100/65">
                {receiveIds.length} asset{receiveIds.length === 1 ? "" : "s"}{" "}
                selected
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/10 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Live projection edge
              </p>
              <p className="mt-1 text-xs font-semibold text-muted-foreground">
                A quick comparison only — the formal review uses the trade
                analyzer.
              </p>
            </div>
            <p
              className={cn(
                "text-3xl font-black italic tabular-nums",
                liveDelta > 0
                  ? "text-emerald-300"
                  : liveDelta < 0
                    ? "text-rose-300"
                    : "text-foreground",
              )}
            >
              {liveDelta >= 0 ? "+" : ""}
              {liveDelta.toFixed(1)}
            </p>
          </div>

          {analysisError && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {analysisError}
            </p>
          )}

          {analysisIsCurrent ? (
            <div className="rounded-2xl border border-emerald-300/25 bg-emerald-500/10 p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100">
                Analysis ready. Review the final trade before sending it.
              </p>
            </div>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Select players from both sides, then run analysis to see value
                differential.
              </p>
            </div>
          )}
          <div className="flex flex-col gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-bold text-muted-foreground">
                Run analysis after every selection change. Sending is locked
                until the current offer has a fresh analysis.
              </p>
              <textarea
                value={tradeMessage}
                onChange={(event) => setTradeMessage(event.target.value)}
                placeholder="Optional message to the other manager..."
                className="min-h-20 w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-bold text-foreground outline-none transition focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/15 sm:w-[28rem]"
              />
              {sendError ? (
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                  {sendError}
                </p>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog
        open={isAnalysisReviewOpen}
        onOpenChange={setIsAnalysisReviewOpen}
      >
        <DialogContent className="max-w-2xl border-cfb-brand/30 bg-[#081321] text-foreground">
          <DialogHeader>
            <DialogTitle className="pr-10 text-2xl font-black uppercase italic tracking-tight sm:text-3xl">
              Review Trade Offer
            </DialogTitle>
            <DialogDescription className="text-sm font-semibold leading-6 text-muted-foreground">
              Review the selected players and the current trade outlook before
              sending the offer.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-red-300/20 bg-red-500/10 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-100">
                You send
              </p>
              <p className="mt-2 text-2xl font-black tabular-nums">
                {analysis?.give_value?.toFixed(2) ?? "N/A"}
              </p>
              <p className="mt-3 text-xs font-semibold leading-5 text-muted-foreground">
                {selectedGiveRows.map((row) => row.name).join(", ") ||
                  "No players selected"}
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-500/10 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100">
                You receive
              </p>
              <p className="mt-2 text-2xl font-black tabular-nums">
                {analysis?.receive_value?.toFixed(2) ?? "N/A"}
              </p>
              <p className="mt-3 text-xs font-semibold leading-5 text-muted-foreground">
                {selectedReceiveRows.map((row) => row.name).join(", ") ||
                  "No players selected"}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Trade verdict
            </p>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
              <p className="text-2xl font-black text-primary">
                {analysis?.verdict ?? "Analysis unavailable"}
              </p>
              <p
                className={cn(
                  "text-xl font-black tabular-nums",
                  (analysis?.delta ?? 0) >= 0
                    ? "text-emerald-300"
                    : "text-red-300",
                )}
              >
                {analysis?.delta === null || analysis?.delta === undefined
                  ? "N/A"
                  : `${analysis.delta >= 0 ? "+" : ""}${analysis.delta.toFixed(2)}`}
              </p>
            </div>
          </div>

          <DialogFooter className="gap-3 sm:gap-3">
            <Button
              variant="outline"
              onClick={() => setIsAnalysisReviewOpen(false)}
            >
              Keep Editing
            </Button>
            <Button disabled={!sendEnabled} onClick={handleSendTrade}>
              {createOfferMutation.isPending
                ? "Sending..."
                : counteringOfferId
                  ? "Send Final Counter"
                  : "Send Final Trade"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isTradeOfferRoute}
        onOpenChange={(open) => {
          if (!open) closeFocusedOffer();
        }}
      >
        <DialogContent className="max-w-4xl border-cfb-brand/30 bg-[#081321] text-foreground">
          <DialogHeader>
            <DialogTitle className="pr-8 text-3xl font-black uppercase italic tracking-tight">
              Review Trade Offer
            </DialogTitle>
            <DialogDescription className="text-sm font-semibold leading-6 text-muted-foreground">
              Review the complete league trade without leaving the conversation
              that shared it.
            </DialogDescription>
          </DialogHeader>

          {focusedOfferQuery.isLoading ? (
            <p className="py-8 text-center text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">
              Loading trade offer...
            </p>
          ) : null}
          {focusedOfferUnavailable ? (
            <div className="rounded-2xl border border-red-300/25 bg-red-500/10 p-5">
              <p className="text-sm font-black text-red-100">
                This trade is unavailable.
              </p>
              <p className="mt-2 text-xs font-semibold leading-5 text-red-100/80">
                The offer may have been removed, belong to another league, or
                the link is invalid. Your league was not changed.
              </p>
            </div>
          ) : null}
          {focusedOffer
            ? (() => {
                const offer = focusedOffer;
                const proposingTeam = teams.find(
                  (team) => team.id === offer.proposing_team_id,
                );
                const receivingTeam = teams.find(
                  (team) => team.id === offer.receiving_team_id,
                );
                const proposingSends = offer.items.filter(
                  (item) => item.team_id === offer.proposing_team_id,
                );
                const receivingSends = offer.items.filter(
                  (item) => item.team_id === offer.receiving_team_id,
                );
                return (
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                          League trade
                        </p>
                        <p className="mt-2 text-xl font-black text-foreground">
                          {proposingTeam?.name ?? "Proposing Team"}{" "}
                          <span className="px-1 text-primary">→</span>{" "}
                          {receivingTeam?.name ?? "Receiving Team"}
                        </p>
                      </div>
                      <span className="rounded-full border border-primary/35 bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                        {formatTradeStatus(offer.status)}
                      </span>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="rounded-2xl border border-red-300/20 bg-red-500/10 p-5">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-100">
                          {proposingTeam?.name ?? "Proposing Team"} gives
                        </p>
                        <div className="mt-4 space-y-3">
                          {proposingSends.length ? (
                            proposingSends.map((item) => (
                              <div
                                key={item.id}
                                className="rounded-xl border border-white/10 bg-black/10 px-4 py-3"
                              >
                                <p className="font-black text-foreground">
                                  {item.player_name ??
                                    `Player ${item.player_id ?? ""}`}
                                </p>
                                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                                  {[item.player_position, item.player_school]
                                    .filter(Boolean)
                                    .join(" · ") || "League asset"}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm font-bold text-muted-foreground">
                              No players listed
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="rounded-2xl border border-emerald-300/20 bg-emerald-500/10 p-5">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100">
                          {receivingTeam?.name ?? "Receiving Team"} gives
                        </p>
                        <div className="mt-4 space-y-3">
                          {receivingSends.length ? (
                            receivingSends.map((item) => (
                              <div
                                key={item.id}
                                className="rounded-xl border border-white/10 bg-black/10 px-4 py-3"
                              >
                                <p className="font-black text-foreground">
                                  {item.player_name ??
                                    `Player ${item.player_id ?? ""}`}
                                </p>
                                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                                  {[item.player_position, item.player_school]
                                    .filter(Boolean)
                                    .join(" · ") || "League asset"}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm font-bold text-muted-foreground">
                              No players listed
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                    {offer.message ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">
                          Manager note
                        </p>
                        <p className="mt-2 text-sm font-semibold leading-6 text-muted-foreground">
                          {offer.message}
                        </p>
                      </div>
                    ) : null}
                  </div>
                );
              })()
            : null}

          <DialogFooter className="sticky bottom-0 border-t border-white/10 bg-[#081321]/95 pt-3 backdrop-blur">
            <Button variant="outline" onClick={closeFocusedOffer}>
              {focusedOfferReturnPath.startsWith("/chats")
                ? "Back to league chat"
                : "Close"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.2em] text-primary">
            Trade Offers
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 p-6">
          {offersQuery.isLoading ? (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Loading trade offers...
            </p>
          ) : null}
          {offersQuery.isError ? (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {formatTradeError(
                offersQuery.error,
                "Unable to load trade offers.",
              )}
            </p>
          ) : null}
          {!offersQuery.isLoading && !offersQuery.data?.data.length ? (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              No trade offers yet.
            </p>
          ) : null}
          {(offersQuery.data?.data ?? []).map((offer) => {
            const proposingTeam = teams.find(
              (team) => team.id === offer.proposing_team_id,
            );
            const receivingTeam = teams.find(
              (team) => team.id === offer.receiving_team_id,
            );
            const giveItems = offer.items.filter(
              (item) => item.team_id === offer.proposing_team_id,
            );
            const receiveItems = offer.items.filter(
              (item) => item.team_id === offer.receiving_team_id,
            );
            const canAccept =
              offer.status === "proposed" &&
              receivingTeam?.owner_user_id === user?.id;
            const canCancel =
              ["proposed", "commissioner_review"].includes(offer.status) &&
              proposingTeam?.owner_user_id === user?.id;
            const canCounter =
              offer.status === "proposed" &&
              receivingTeam?.owner_user_id === user?.id;
            const canReview =
              offer.status === "commissioner_review" &&
              league?.commissioner_user_id === user?.id;
            return (
              <div
                key={offer.id}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                        {proposingTeam?.name ?? "Proposing Team"} →{" "}
                        {receivingTeam?.name ?? "Receiving Team"}
                      </p>
                      <p className="mt-1 text-sm font-black uppercase tracking-[0.12em] text-foreground">
                        {formatTradeStatus(offer.status)}
                      </p>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-200/80">
                          {proposingTeam?.name ?? "Team"} gives
                        </p>
                        <p className="mt-1 text-sm font-bold text-muted-foreground">
                          {giveItems
                            .map(
                              (item) =>
                                item.player_name ?? `Player ${item.player_id}`,
                            )
                            .join(", ")}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-200/80">
                          {receivingTeam?.name ?? "Team"} gives
                        </p>
                        <p className="mt-1 text-sm font-bold text-muted-foreground">
                          {receiveItems
                            .map(
                              (item) =>
                                item.player_name ?? `Player ${item.player_id}`,
                            )
                            .join(", ")}
                        </p>
                      </div>
                    </div>
                    {offer.status === "accepted_pending" &&
                    offer.process_after ? (
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-200">
                        Processes after{" "}
                        {new Date(offer.process_after).toLocaleString()}
                      </p>
                    ) : null}
                    {offer.failure_reason ? (
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                        {offer.failure_reason}
                      </p>
                    ) : null}
                    {offer.countered_from_trade_id ? (
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-200">
                        Counter offer to trade #{offer.countered_from_trade_id}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {canAccept ? (
                      <>
                        <Button
                          className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                          disabled={tradeActionMutation.isPending}
                          onClick={() =>
                            tradeActionMutation.mutate({
                              tradeId: offer.id,
                              action: "accept",
                            })
                          }
                        >
                          Accept
                        </Button>
                        <Button
                          variant="outline"
                          className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                          disabled={tradeActionMutation.isPending}
                          onClick={() =>
                            tradeActionMutation.mutate({
                              tradeId: offer.id,
                              action: "reject",
                            })
                          }
                        >
                          Decline
                        </Button>
                      </>
                    ) : null}
                    {canCounter ? (
                      <Button
                        variant="outline"
                        className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                        disabled={
                          tradeActionMutation.isPending ||
                          createOfferMutation.isPending
                        }
                        onClick={() => beginCounterOffer(offer)}
                      >
                        Counter
                      </Button>
                    ) : null}
                    {canCancel ? (
                      <Button
                        variant="outline"
                        className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                        disabled={tradeActionMutation.isPending}
                        onClick={() =>
                          tradeActionMutation.mutate({
                            tradeId: offer.id,
                            action: "cancel",
                          })
                        }
                      >
                        Unsend Offer
                      </Button>
                    ) : null}
                    {canReview ? (
                      <>
                        <Button
                          className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                          disabled={tradeActionMutation.isPending}
                          onClick={() =>
                            tradeActionMutation.mutate({
                              tradeId: offer.id,
                              action: "commissioner/approve",
                            })
                          }
                        >
                          Approve
                        </Button>
                        <Button
                          variant="outline"
                          className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                          disabled={tradeActionMutation.isPending}
                          onClick={() =>
                            tradeActionMutation.mutate({
                              tradeId: offer.id,
                              action: "commissioner/veto",
                            })
                          }
                        >
                          Veto
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
          {actionError ? (
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
              {actionError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card className="rounded-[2rem] border border-emerald-400/20 bg-emerald-500/10">
        <CardContent className="flex items-center gap-3 p-5 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-100">
          <Users className="h-4 w-4" />
          Trade value is calculated from your league rosters and weekly
          projections.
        </CardContent>
      </Card>
    </div>
  );
}
