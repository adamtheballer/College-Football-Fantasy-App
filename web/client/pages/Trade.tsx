import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRightLeft,
  ChevronRight,
  SendHorizontal,
  ShieldAlert,
  Users,
} from "lucide-react";

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
import {
  useLeagueDetail,
  useLeagues,
  useLeagueWorkspace,
} from "@/hooks/use-leagues";
import { useLeagueTeams, useTeamRoster } from "@/hooks/use-teams";
import { toast } from "@/components/ui/use-toast";
import { apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";
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

type TradeProposalPayload = {
  league_id: number;
  from_team_id: number;
  to_team_id: number;
  give_ids: number[];
  receive_ids: number[];
  note?: string;
};

type TradeProposalResponse = {
  proposal_ref: string;
  message: string;
};

type TradeRow = {
  rosterEntryId: number;
  playerId: number;
  name: string;
  position: string;
  school: string;
  slot: string;
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
  const navigate = useNavigate();
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(50, true);
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();

  const parsedLeagueId =
    leagueIdParam && /^\d+$/.test(leagueIdParam) ? Number(leagueIdParam) : undefined;
  const fallbackLeagueId = activeLeagueId ?? leagues[0]?.id;
  const leagueId = parsedLeagueId ?? fallbackLeagueId;

  const { data: league } = useLeagueDetail(leagueId, Boolean(leagueId));
  const { data: workspace } = useLeagueWorkspace(leagueId, Boolean(leagueId));
  const { data: teamsPayload } = useLeagueTeams(leagueId, Boolean(leagueId));

  const teams = teamsPayload?.data ?? [];
  const ownedTeamId = workspace?.owned_team?.id ?? null;
  const opponentTeams = useMemo(
    () => teams.filter((team) => team.id !== ownedTeamId),
    [ownedTeamId, teams]
  );

  const [opponentTeamId, setOpponentTeamId] = useState<number | null>(null);
  const [giveIds, setGiveIds] = useState<number[]>([]);
  const [receiveIds, setReceiveIds] = useState<number[]>([]);
  const [analysis, setAnalysis] = useState<TradeAnalyzeResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [proposalMessage, setProposalMessage] = useState<string | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
  const theirRows = useMemo(() => toTradeRows(theirRosterPayload?.data), [theirRosterPayload?.data]);
  const giveSet = useMemo(() => new Set(giveIds), [giveIds]);
  const receiveSet = useMemo(() => new Set(receiveIds), [receiveIds]);

  useEffect(() => {
    const parsedPlayerId =
      playerIdParam && /^\d+$/.test(playerIdParam) ? Number(playerIdParam) : null;
    if (!parsedPlayerId || !theirRows.length) return;
    if (theirRows.some((row) => row.playerId === parsedPlayerId)) {
      setReceiveIds((current) =>
        current.includes(parsedPlayerId) ? current : [...current, parsedPlayerId]
      );
    }
  }, [playerIdParam, theirRows]);

  useEffect(() => {
    setAnalysis(null);
    setAnalysisError(null);
    setProposalMessage(null);
    setProposalError(null);
  }, [giveIds, receiveIds, opponentTeamId, leagueId]);

  const opponentTeam = teams.find((team) => team.id === opponentTeamId) ?? null;
  const ownedTeam = teams.find((team) => team.id === ownedTeamId) ?? null;
  const canSubmitTrade = Boolean(
    league && ownedTeamId && opponentTeamId && giveIds.length && receiveIds.length
  );

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
    if (!league || !giveIds.length || !receiveIds.length) {
      return;
    }
    const payload: TradeAnalyzePayload = {
      receive_ids: receiveIds,
      give_ids: giveIds,
      season: league.season_year,
      week: Number(workspace?.matchup_summary?.week ?? 1),
      league_size: league.max_teams,
      roster_slots: toTradeRosterSlots(league.settings?.roster_slots_json),
    };
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await apiPost<TradeAnalyzeResult>("/trades/analyze", payload);
      setAnalysis(result);
    } catch (error) {
      setAnalysis(null);
      const detail =
        error instanceof Error ? error.message : "Unable to analyze trade.";
      if (detail.toLowerCase().includes("draft")) {
        setAnalysisError(
          "Trade analysis should not be blocked by draft status. Try sending the offer directly."
        );
        return;
      }
      setAnalysisError(detail);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSendOffer = async () => {
    if (!league || !ownedTeamId || !opponentTeamId || !giveIds.length || !receiveIds.length) {
      return;
    }
    const payload: TradeProposalPayload = {
      league_id: league.id,
      from_team_id: ownedTeamId,
      to_team_id: opponentTeamId,
      give_ids: giveIds,
      receive_ids: receiveIds,
    };
    setIsSubmitting(true);
    setProposalError(null);
    setProposalMessage(null);
    try {
      const response = await apiPost<TradeProposalResponse>("/trades/propose", payload);
      setProposalMessage(response.message);
      toast({
        title: "Trade offer sent",
        description: response.message,
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unable to send trade offer.";
      setProposalError(detail);
      toast({
        title: "Unable to send trade offer",
        description: detail,
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!leagueId) {
    return (
      <div className="mx-auto max-w-4xl py-12">
        <Card className="rounded-[2rem] border border-white/10 bg-card/40">
          <CardContent className="space-y-4 p-10 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.25em] text-muted-foreground/70">
              {leaguesLoading ? "Loading leagues..." : "No leagues available for trade yet."}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button
                className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={() => navigate("/leagues")}
              >
                Open Leagues
              </Button>
              <Button
                variant="outline"
                className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={() => navigate("/draft")}
              >
                Open Draft Tab
              </Button>
            </div>
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

      {league?.status === "pre_draft" && (
        <Card className="rounded-[2rem] border border-blue-400/20 bg-blue-500/10">
          <CardContent className="p-5 text-[10px] font-black uppercase tracking-[0.18em] text-blue-100">
            Trade planning and offer flow are available before the draft starts.
          </CardContent>
        </Card>
      )}

      {!ownedTeamId && (
        <Card className="rounded-[2rem] border border-amber-400/30 bg-amber-500/10">
          <CardContent className="space-y-3 p-6">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-100">
              You need a team in this league before proposing trades.
            </p>
            <Button
              asChild
              variant="outline"
              className="h-10 rounded-xl border-amber-300/30 text-[10px] font-black uppercase tracking-[0.18em] text-amber-100"
            >
              <Link to={`/league/${leagueId}`}>Open League Setup</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardContent className="grid gap-4 p-6 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Your Team
            </p>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-black uppercase tracking-[0.14em] text-foreground">
              {ownedTeam?.name ?? "Loading team..."}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Trade Partner
            </p>
            <Select
              value={opponentTeamId ? String(opponentTeamId) : ""}
              onValueChange={(value) => setOpponentTeamId(Number(value))}
              disabled={!opponentTeams.length}
            >
              <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.16em]">
                <SelectValue placeholder="Select team" />
              </SelectTrigger>
              <SelectContent>
                {opponentTeams.length > 0 ? (
                  opponentTeams.map((team: Team) => (
                    <SelectItem key={team.id} value={String(team.id)}>
                      {team.name}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="no-opponents" disabled>
                    No opponent teams available
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <TradeList
          title="Players You Give"
          subtitle={myRosterLoading ? "Loading roster..." : "Select one or more players"}
          rows={myRows}
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
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
              disabled={!canSubmitTrade || isSubmitting}
              onClick={handleSendOffer}
            >
              <SendHorizontal className="mr-2 h-4 w-4" />
              {isSubmitting ? "Sending..." : "Send Offer"}
            </Button>
            <Button
              className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
              disabled={isAnalyzing || !giveIds.length || !receiveIds.length || !league}
              onClick={handleAnalyze}
            >
              {isAnalyzing ? "Analyzing..." : "Analyze Trade"}
              {!isAnalyzing && <ChevronRight className="ml-2 h-4 w-4" />}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 p-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Giving
              </p>
              <p className="mt-2 text-2xl font-black italic text-foreground">{giveIds.length}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Receiving
              </p>
              <p className="mt-2 text-2xl font-black italic text-foreground">{receiveIds.length}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                League Size
              </p>
              <p className="mt-2 text-2xl font-black italic text-foreground">
                {league?.max_teams ?? "-"}
              </p>
            </div>
          </div>

          {analysisError && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {analysisError}
            </p>
          )}

          {proposalError && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
              {proposalError}
            </p>
          )}

          {proposalMessage && (
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-300">
              {proposalMessage}
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
                  Basic Estimate
                </p>
                <p className="mt-2 text-xl font-black text-primary">{analysis.verdict}</p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Select players from both sides, then run a basic estimate to see value differential.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-[2rem] border border-emerald-400/20 bg-emerald-500/10">
        <CardContent className="flex items-center gap-3 p-5 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-100">
          <Users className="h-4 w-4" />
          Basic trade value uses local roster and projection data only; schedule context is neutral unless backend analysis is added.
        </CardContent>
      </Card>
    </div>
  );
}
