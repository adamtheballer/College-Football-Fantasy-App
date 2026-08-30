import { useState } from "react";
import { Lock } from "lucide-react";

import { type RosterPointMode, finalPregameProjectionDetail, formatRosterGameKickoff, formatRosterPointValue, liveGameStatusLabel, liveProjectionDetail } from "@/components/league/RosterSlotTable";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { SurfaceCard } from "@/components/fantasy";
import { usePlayerCard } from "@/hooks/use-players";
import { managerTeamName } from "@/lib/manager-team-name";
import { PlayerAvailabilityIndicator } from "@/lib/playerAvailability";
import { rosterPlayerGameState, rosterPlayerIsLive } from "@/lib/rosterGameState";
import type { LeagueMatchupTeam, LeagueRosterPlayer } from "@/types/league";

const reserveSlots = new Set(["BENCH", "IR"]);

const rosterSlot = (player: LeagueRosterPlayer) =>
  (player.slot ?? player.roster_slot ?? "").toUpperCase();

const isReservePlayer = (player: LeagueRosterPlayer) =>
  player.is_ir === true || reserveSlots.has(rosterSlot(player));

const startersFor = (team: LeagueMatchupTeam | null) =>
  (team?.roster ?? []).filter((player) => !isReservePlayer(player));

const reservesFor = (team: LeagueMatchupTeam | null) =>
  (team?.roster ?? []).filter(isReservePlayer);

const slotOrder = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];

const sortBySlot = (players: LeagueRosterPlayer[]) =>
  [...players].sort((left, right) => {
    const leftSlot = rosterSlot(left);
    const rightSlot = rosterSlot(right);
    const leftRank = slotOrder.indexOf(leftSlot);
    const rightRank = slotOrder.indexOf(rightSlot);
    if (leftRank !== rightRank) return leftRank - rightRank;
    return (left.slot_index ?? 0) - (right.slot_index ?? 0);
  });

const compactSlot = (player?: LeagueRosterPlayer) =>
  player ? (player.display_label ?? rosterSlot(player) ?? "—").toUpperCase() : "—";

const compactPointValue = (player: LeagueRosterPlayer | undefined, pointMode: RosterPointMode) => {
  return player ? formatRosterPointValue(player, pointMode) : "—";
};

const pointModeForMatchupStatus = (status?: string | null): RosterPointMode =>
  ["live", "final", "stat_corrected", "corrected", "delayed"].includes((status ?? "").toLowerCase())
    ? "live"
    : "projected";

const playerGameIsFinal = (player?: LeagueRosterPlayer) =>
  ["final", "post"].includes(rosterPlayerGameState(player));

const playerGameIsLive = (player?: LeagueRosterPlayer) =>
  Boolean(player?.player_id && rosterPlayerIsLive(player));

export const compactMatchupPlayerName = (name?: string | null) => {
  const parts = name?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (parts.length < 2) return name?.trim() || "No starter set";
  return `${parts[0][0]?.toUpperCase() ?? ""}. ${parts.slice(1).join(" ")}`;
};

export const formatPlayerGameMatchup = (player?: LeagueRosterPlayer) => {
  if (!player?.player_id) return "Open slot";
  const school = player.school ?? player.player_school ?? "School TBD";
  if (!player.opponent) return school;

  // The API supplies the player's team's venue. Keep the road team first in the
  // compact matchup notation so it reads consistently across the app.
  return player.game_location === "home"
    ? `${player.opponent} @ ${school}`
    : player.game_location === "neutral"
      ? `${school} vs ${player.opponent} · Neutral`
      : `${school} @ ${player.opponent}`;
};

export const formatPlayerGameTime = (player?: LeagueRosterPlayer) =>
  player?.player_id ? formatRosterGameKickoff(player.game_start_at) : "Kickoff TBD";

export const formatPlayerGameContext = (player?: LeagueRosterPlayer) => {
  const matchup = formatPlayerGameMatchup(player);
  const kickoff = formatPlayerGameTime(player);
  return matchup === "Open slot" ? matchup : `${matchup} · ${kickoff}`;
};

function CompactMatchupPlayer({
  player,
  align,
  pointMode,
  onSelect,
  desktop = false,
}: {
  player?: LeagueRosterPlayer;
  align: "left" | "right";
  pointMode: RosterPointMode;
  onSelect?: (player: LeagueRosterPlayer) => void;
  desktop?: boolean;
}) {
  const hasPlayer = Boolean(player?.player_id && player.player_name);
  const points = compactPointValue(player, pointMode);
  const liveDetail = player ? liveProjectionDetail(player) : null;
  const finalPregameProjection = player ? finalPregameProjectionDetail(player) : null;
  const isLiveGame = playerGameIsLive(player);
  const hasPossession = isLiveGame && player?.team_has_possession === true;
  const isFinalGame = playerGameIsFinal(player);
  const hasActualPoints = isLiveGame || isFinalGame || ["live", "stale"].includes((player?.live_scoring_status ?? "").toLowerCase());
  const playerName = hasPlayer ? compactMatchupPlayerName(player?.player_name) : "No starter set";
  const gameMatchup = hasPlayer ? formatPlayerGameMatchup(player) : "Set a starter in your roster";
  const gameTime = hasPlayer ? formatPlayerGameTime(player) : "Kickoff TBD";
  const gameStatus = player ? liveGameStatusLabel(player) : null;
  const gameStatLine = player?.game_stat_line ?? (isFinalGame ? player?.final_game_stat_line : null);
  const interactive = Boolean(hasPlayer && player && onSelect);
  const openPlayerCard = () => {
    if (player && onSelect) onSelect(player);
  };
  const interactiveClassName = interactive
    ? "w-full rounded-md text-left transition-colors hover:bg-white/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70"
    : "";
  const playerNameClassName = desktop ? "text-[16px] leading-5" : "text-[12px] leading-4";

  // A flex row that is justified to the right moves the player name whenever
  // the projection or name changes width. Keep a fixed projection rail on
  // the opponent side instead, then anchor all three player-detail lines to
  // the same content column.
  if (align === "right") {
    const content = (
      <>
        <span className={`self-center text-left text-[11px] font-black tabular-nums ${hasActualPoints ? "text-cfb-brand" : "text-cfb-text-primary"}`}>
          {isLiveGame ? <Lock data-lineup-lock aria-label="Game in progress — lineup locked" className="mb-0.5 h-2.5 w-2.5 text-cfb-text-muted" /> : null}
          <span className="block">{points}</span>
          {liveDetail ? <span data-player-final-status={isFinalGame ? "true" : undefined} className={`block ${isFinalGame ? "text-[9px] font-black text-cfb-brand" : "text-[8px] font-semibold text-cfb-text-muted"}`}>{liveDetail}</span> : null}
          {finalPregameProjection ? <span data-player-final-pregame-projection className="block text-[7px] font-semibold text-cfb-brand">{finalPregameProjection}</span> : null}
        </span>
        <div className="min-w-0">
          <p className={`flex min-w-0 items-center gap-1 truncate font-black text-cfb-text-primary ${playerNameClassName} ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
            <PlayerAvailabilityIndicator status={player?.injury_status}>
              <span className="truncate">{playerName}</span>
            </PlayerAvailabilityIndicator>
            {hasPossession ? <span role="img" aria-label="Team has possession" className="shrink-0 text-[11px] leading-none">🏈</span> : null}
            {isFinalGame ? <Lock aria-label="Game final" className="h-2.5 w-2.5 shrink-0 text-cfb-text-muted" /> : null}
          </p>
          <p data-player-game-matchup className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
            {gameMatchup}
          </p>
          {gameStatus ? (
            <p data-player-live-game-status className="truncate text-[9px] font-black leading-3 text-cfb-brand">{gameStatus}</p>
          ) : !isFinalGame ? (
            <p data-player-game-time className="truncate text-[9px] font-bold leading-3 text-cfb-text-muted">{gameTime}</p>
          ) : null}
          {gameStatLine ? (
            <p data-player-game-stat-line data-player-final-stat-line={isFinalGame ? "true" : undefined} title={gameStatLine} className="truncate text-[8px] font-semibold leading-3 text-cfb-text-muted">{gameStatLine}</p>
          ) : null}
        </div>
      </>
    );
    return (
      interactive ? (
        <button type="button" data-mobile-matchup-player="right" data-live-game-state={isLiveGame ? "live" : "unavailable"} data-has-possession={hasPossession ? "true" : "false"} aria-label={`Open ${playerName} player card`} onClick={openPlayerCard} className={`grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-x-1.5 ${interactiveClassName}`}>
          {content}
        </button>
      ) : (
        <div data-mobile-matchup-player="right" data-live-game-state={isLiveGame ? "live" : "unavailable"} data-has-possession={hasPossession ? "true" : "false"} className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-x-1.5 text-left">
          {content}
        </div>
      )
    );
  }

  const content = (
    <>
      <div className="min-w-0">
        <p className={`flex min-w-0 items-center gap-1 truncate font-black text-cfb-text-primary ${playerNameClassName} ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
          <PlayerAvailabilityIndicator status={player?.injury_status}>
            <span className="truncate">{playerName}</span>
          </PlayerAvailabilityIndicator>
          {hasPossession ? <span role="img" aria-label="Team has possession" className="shrink-0 text-[11px] leading-none">🏈</span> : null}
          {isFinalGame ? <Lock aria-label="Game final" className="h-2.5 w-2.5 shrink-0 text-cfb-text-muted" /> : null}
        </p>
        <p data-player-game-matchup className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
          {gameMatchup}
        </p>
        {gameStatus ? (
          <p data-player-live-game-status className="truncate text-[9px] font-black leading-3 text-cfb-brand">{gameStatus}</p>
        ) : !isFinalGame ? (
          <p data-player-game-time className="truncate text-[9px] font-bold leading-3 text-cfb-text-muted">{gameTime}</p>
        ) : null}
        {gameStatLine ? (
          <p data-player-game-stat-line data-player-final-stat-line={isFinalGame ? "true" : undefined} title={gameStatLine} className="truncate text-[8px] font-semibold leading-3 text-cfb-text-muted">{gameStatLine}</p>
        ) : null}
      </div>
      <span className={`self-center text-right text-[11px] font-black tabular-nums ${hasActualPoints ? "text-cfb-brand" : "text-cfb-text-primary"}`}>
        {isLiveGame ? <Lock data-lineup-lock aria-label="Game in progress — lineup locked" className="mb-0.5 h-2.5 w-2.5 text-cfb-text-muted" /> : null}
        <span className="block">{points}</span>
        {liveDetail ? <span data-player-final-status={isFinalGame ? "true" : undefined} className={`block ${isFinalGame ? "text-[9px] font-black text-cfb-brand" : "text-[8px] font-semibold text-cfb-text-muted"}`}>{liveDetail}</span> : null}
        {finalPregameProjection ? <span data-player-final-pregame-projection className="block text-[7px] font-semibold text-cfb-brand">{finalPregameProjection}</span> : null}
      </span>
    </>
  );

  return (
    interactive ? (
      <button type="button" data-mobile-matchup-player="left" data-live-game-state={isLiveGame ? "live" : "unavailable"} data-has-possession={hasPossession ? "true" : "false"} aria-label={`Open ${playerName} player card`} onClick={openPlayerCard} className={`grid min-w-0 grid-cols-[minmax(0,1fr)_2.75rem] gap-x-1.5 ${interactiveClassName}`}>
        {content}
      </button>
    ) : (
      <div data-mobile-matchup-player="left" data-live-game-state={isLiveGame ? "live" : "unavailable"} data-has-possession={hasPossession ? "true" : "false"} className="grid min-w-0 grid-cols-[minmax(0,1fr)_2.75rem] gap-x-1.5 text-left">
        {content}
      </div>
    )
  );
}

function CompactMatchupLineup({
  title,
  myPlayers,
  opponentPlayers,
  pointMode,
  testId,
  showHeader = true,
  desktop = false,
  myTeamName,
  opponentTeamName,
  onPlayerSelect,
}: {
  title: string;
  myPlayers: LeagueRosterPlayer[];
  opponentPlayers: LeagueRosterPlayer[];
  pointMode: RosterPointMode;
  testId: string;
  showHeader?: boolean;
  desktop?: boolean;
  myTeamName?: string;
  opponentTeamName?: string;
  onPlayerSelect?: (player: LeagueRosterPlayer) => void;
}) {
  const rowCount = Math.max(myPlayers.length, opponentPlayers.length);
  const sectionClassName = desktop
    ? "hidden overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised md:block"
    : "overflow-hidden border-y border-cfb-border-subtle bg-cfb-surface-raised/70 md:hidden";
  const centerRailClassName = desktop ? "w-20" : "w-14";
  const rowClassName = desktop
    ? "relative z-10 grid min-h-[92px] grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] items-stretch px-5"
    : "relative z-10 grid min-h-[72px] grid-cols-[minmax(0,1fr)_3.5rem_minmax(0,1fr)] items-stretch px-3";
  const playerCellClassName = desktop ? "py-3" : "py-2";
  const slotCellClassName = desktop ? "min-h-[92px]" : "min-h-[72px]";

  return (
    <section data-testid={testId} className={sectionClassName}>
      {desktop ? (
        <div className="grid grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] border-b border-cfb-border-subtle bg-cfb-surface/70 px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
          <span className="text-cfb-text-primary">{myTeamName}</span>
          <span className="text-center">Slot</span>
          <span className="text-right text-cfb-text-primary">{opponentTeamName}</span>
        </div>
      ) : null}
      {showHeader ? (
        <div className="flex items-center justify-between bg-cfb-surface/70 px-4 py-3">
          <h2 className="text-[11px] font-black uppercase tracking-[0.17em] text-cfb-text-primary">{title}</h2>
          <span className="text-[9px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">{pointMode === "live" ? "Live" : "Proj"}</span>
        </div>
      ) : null}
      <div className="relative">
        <div
          aria-hidden="true"
          data-mobile-slot-rail
          data-desktop-slot-rail={desktop ? "true" : undefined}
          className={`pointer-events-none absolute inset-y-0 left-1/2 z-0 ${centerRailClassName} -translate-x-1/2 border-x border-[#101d31] bg-[#060c17]`}
        />
        {Array.from({ length: rowCount }, (_, index) => {
          const myPlayer = myPlayers[index];
          const opponentPlayer = opponentPlayers[index];
          const slot = compactSlot(myPlayer ?? opponentPlayer);
          const hasFollowingRow = index < rowCount - 1;
          const myPlayerIsLive = playerGameIsLive(myPlayer);
          const opponentPlayerIsLive = playerGameIsLive(opponentPlayer);
          return (
            <div
              key={`${slot}-${index}`}
              data-mobile-matchup-row
              data-desktop-matchup-row={desktop ? "true" : undefined}
              className={rowClassName}
            >
              <div data-mobile-player-live={myPlayerIsLive ? "true" : "false"} className={`flex min-w-0 items-center ${playerCellClassName} ${hasFollowingRow ? "border-b-2 border-[#07101f]" : ""} ${myPlayerIsLive ? "bg-slate-100/[0.10]" : ""}`}>
                <CompactMatchupPlayer player={myPlayer} align="left" pointMode={pointMode} onSelect={onPlayerSelect} desktop={desktop} />
              </div>
              <span data-mobile-slot-column data-desktop-slot-column={desktop ? "true" : undefined} className={`inline-flex ${slotCellClassName} whitespace-nowrap items-center justify-center px-1 text-[9px] font-black uppercase tracking-[0.02em] text-cfb-text-secondary`}>
                {slot}
              </span>
              <div data-mobile-player-live={opponentPlayerIsLive ? "true" : "false"} className={`flex min-w-0 items-center ${playerCellClassName} ${hasFollowingRow ? "border-b-2 border-[#07101f]" : ""} ${opponentPlayerIsLive ? "bg-slate-100/[0.10]" : ""}`}>
                <CompactMatchupPlayer player={opponentPlayer} align="right" pointMode={pointMode} onSelect={onPlayerSelect} desktop={desktop} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function SideBySideMatchup({
  myTeam,
  opponentTeam,
  leagueId,
  scoringStatus,
}: {
  myTeam: LeagueMatchupTeam | null;
  opponentTeam: LeagueMatchupTeam | null;
  leagueId?: number | string;
  scoringStatus?: string | null;
}) {
  const [selectedPlayer, setSelectedPlayer] = useState<LeagueRosterPlayer | null>(null);
  const myStarters = sortBySlot(startersFor(myTeam));
  const opponentStarters = sortBySlot(startersFor(opponentTeam));
  const myReserves = sortBySlot(reservesFor(myTeam));
  const opponentReserves = sortBySlot(reservesFor(opponentTeam));
  const selectedPlayerCardQuery = usePlayerCard(selectedPlayer?.player_id, Boolean(selectedPlayer?.player_id));
  const selectedProjection = selectedPlayer?.projected_points ?? selectedPlayer?.weekly_projected_fantasy_points;
  const numericLeagueId = typeof leagueId === "number" ? leagueId : Number(leagueId);
  const resolvedLeagueId = Number.isFinite(numericLeagueId) && numericLeagueId > 0 ? numericLeagueId : undefined;
  const pointMode = pointModeForMatchupStatus(scoringStatus);

  return (
    <div className="space-y-4 sm:space-y-6">
      <section className="space-y-3">
        <CompactMatchupLineup
          title="Starter matchup"
          myPlayers={myStarters}
          opponentPlayers={opponentStarters}
          pointMode={pointMode}
          testId="mobile-starting-lineup"
          showHeader={false}
          onPlayerSelect={setSelectedPlayer}
        />
        <CompactMatchupLineup
          title="Starter matchup"
          myPlayers={myStarters}
          opponentPlayers={opponentStarters}
          pointMode={pointMode}
          testId="desktop-starting-lineup"
          showHeader={false}
          desktop
          myTeamName={`${managerTeamName(myTeam, "Your Team")} Starters`}
          opponentTeamName={`${managerTeamName(opponentTeam, "Opponent")} Starters`}
          onPlayerSelect={setSelectedPlayer}
        />
      </section>

      <details className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/95 p-0 md:hidden">
        <summary className="flex min-h-[52px] cursor-pointer list-none items-center justify-between px-4 text-[11px] font-black uppercase tracking-[0.16em] text-cfb-text-secondary [&::-webkit-details-marker]:hidden">
          Bench depth
          <span className="text-[9px] text-cfb-text-muted">{myReserves.length} / {opponentReserves.length}</span>
        </summary>
        <div className="border-t border-cfb-border-subtle p-3">
          <CompactMatchupLineup
            title="Bench"
            myPlayers={myReserves}
            opponentPlayers={opponentReserves}
            pointMode={pointMode}
            testId="mobile-bench-lineup"
            onPlayerSelect={setSelectedPlayer}
          />
        </div>
      </details>

      <SurfaceCard variant="default" padding="compact" className="hidden space-y-3 md:block">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-text-muted">
              Bench Depth
            </p>
          </div>
        </div>
        <CompactMatchupLineup
          title="Bench"
          myPlayers={myReserves}
          opponentPlayers={opponentReserves}
          pointMode={pointMode}
          testId="desktop-bench-lineup"
          showHeader={false}
          desktop
          myTeamName={`${managerTeamName(myTeam, "Your Team")} Bench`}
          opponentTeamName={`${managerTeamName(opponentTeam, "Opponent")} Bench`}
          onPlayerSelect={setSelectedPlayer}
        />
      </SurfaceCard>
      {selectedPlayer ? (
        <PlayerCardModal
          card={selectedPlayerCardQuery.data}
          error={selectedPlayerCardQuery.isError}
          leagueId={resolvedLeagueId}
          loading={selectedPlayerCardQuery.isLoading}
          onClose={() => setSelectedPlayer(null)}
          onRetry={() => void selectedPlayerCardQuery.refetch()}
          player={{
            id: selectedPlayer.player_id ?? 0,
            name: selectedPlayer.player_name ?? "Unknown player",
            school: selectedPlayer.school ?? selectedPlayer.player_school,
            position: selectedPlayer.position ?? selectedPlayer.player_position ?? rosterSlot(selectedPlayer),
            rankLabel: selectedPlayer.position ?? selectedPlayer.player_position ?? rosterSlot(selectedPlayer),
            projectedPoints: selectedProjection,
            opponent: selectedPlayer.opponent,
            playerClass: null,
            status: selectedPlayer.status,
            projection: {
              fpts: selectedProjection,
              floor: selectedPlayer.floor ?? undefined,
              ceiling: selectedPlayer.ceiling ?? undefined,
              boomProb: selectedPlayer.boom_prob ?? undefined,
              bustProb: selectedPlayer.bust_prob ?? undefined,
            },
          }}
          title="Matchup Player Card"
        />
      ) : null}
    </div>
  );
}
