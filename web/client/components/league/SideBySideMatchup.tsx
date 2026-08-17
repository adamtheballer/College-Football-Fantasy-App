import { useState } from "react";

import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { SurfaceCard } from "@/components/fantasy";
import { usePlayerCard } from "@/hooks/use-players";
import { formatProjectionDisplay } from "@/lib/projection-display";
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

const compactProjection = (player?: LeagueRosterPlayer) =>
  formatProjectionDisplay(
    player?.projected_points ?? player?.weekly_projected_fantasy_points ?? null,
    player?.projection_status,
  );

export const compactMatchupPlayerName = (name?: string | null) => {
  const parts = name?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (parts.length < 2) return name?.trim() || "No starter set";
  return `${parts[0][0]?.toUpperCase() ?? ""}. ${parts.slice(1).join(" ")}`;
};

const kickoffLabel = (value?: string | null) => {
  if (!value) return "Kickoff TBD";
  const kickoff = new Date(value);
  if (Number.isNaN(kickoff.getTime())) return "Kickoff TBD";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(kickoff);
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
  player?.player_id ? kickoffLabel(player.game_start_at) : "Kickoff TBD";

export const formatPlayerGameContext = (player?: LeagueRosterPlayer) => {
  const matchup = formatPlayerGameMatchup(player);
  const kickoff = formatPlayerGameTime(player);
  return matchup === "Open slot" ? matchup : `${matchup} · ${kickoff}`;
};

function CompactMatchupPlayer({
  player,
  align,
  onSelect,
}: {
  player?: LeagueRosterPlayer;
  align: "left" | "right";
  onSelect?: (player: LeagueRosterPlayer) => void;
}) {
  const hasPlayer = Boolean(player?.player_id && player.player_name);
  const points = compactProjection(player);
  const playerName = hasPlayer ? compactMatchupPlayerName(player?.player_name) : "No starter set";
  const gameMatchup = hasPlayer ? formatPlayerGameMatchup(player) : "Set a starter in your roster";
  const gameTime = hasPlayer ? formatPlayerGameTime(player) : "Kickoff TBD";
  const interactive = Boolean(hasPlayer && player && onSelect);
  const openPlayerCard = () => {
    if (player && onSelect) onSelect(player);
  };
  const interactiveClassName = interactive
    ? "w-full rounded-md text-left transition-colors hover:bg-white/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70"
    : "";

  // A flex row that is justified to the right moves the player name whenever
  // the projection or name changes width. Keep a fixed projection rail on
  // the opponent side instead, then anchor all three player-detail lines to
  // the same content column.
  if (align === "right") {
    const content = (
      <>
        <p className="pt-px text-[11px] font-black tabular-nums text-cfb-pink">{points}</p>
        <div className="min-w-0">
          <p className={`truncate text-[12px] font-black leading-4 text-cfb-text-primary ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
            {playerName}
          </p>
          <p data-player-game-matchup className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
            {gameMatchup}
          </p>
          <p data-player-game-time className="truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
            {gameTime}
          </p>
        </div>
      </>
    );
    return (
      interactive ? (
        <button type="button" data-mobile-matchup-player="right" aria-label={`Open ${playerName} player card`} onClick={openPlayerCard} className={`grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-x-1.5 ${interactiveClassName}`}>
          {content}
        </button>
      ) : (
        <div data-mobile-matchup-player="right" className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-x-1.5 text-left">
          {content}
        </div>
      )
    );
  }

  const content = (
    <>
      <div className="min-w-0">
        <p className={`truncate text-[12px] font-black leading-4 text-cfb-text-primary ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
          {playerName}
        </p>
        <p data-player-game-matchup className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
          {gameMatchup}
        </p>
        <p data-player-game-time className="truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
          {gameTime}
        </p>
      </div>
      <p className="pt-px text-right text-[11px] font-black tabular-nums text-cfb-brand">{points}</p>
    </>
  );

  return (
    interactive ? (
      <button type="button" data-mobile-matchup-player="left" aria-label={`Open ${playerName} player card`} onClick={openPlayerCard} className={`grid min-w-0 grid-cols-[minmax(0,1fr)_2.75rem] gap-x-1.5 ${interactiveClassName}`}>
        {content}
      </button>
    ) : (
      <div data-mobile-matchup-player="left" className="grid min-w-0 grid-cols-[minmax(0,1fr)_2.75rem] gap-x-1.5 text-left">
        {content}
      </div>
    )
  );
}

function CompactMobileLineup({
  title,
  myPlayers,
  opponentPlayers,
  testId,
  showHeader = true,
  onPlayerSelect,
}: {
  title: string;
  myPlayers: LeagueRosterPlayer[];
  opponentPlayers: LeagueRosterPlayer[];
  testId: string;
  showHeader?: boolean;
  onPlayerSelect?: (player: LeagueRosterPlayer) => void;
}) {
  const rowCount = Math.max(myPlayers.length, opponentPlayers.length);

  return (
    <section data-testid={testId} className="overflow-hidden border-y border-cfb-border-subtle bg-cfb-surface-raised/70 md:hidden">
      {showHeader ? (
        <div className="flex items-center justify-between bg-cfb-surface/70 px-4 py-3">
          <h2 className="text-[11px] font-black uppercase tracking-[0.17em] text-cfb-text-primary">{title}</h2>
          <span className="text-[9px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">Points</span>
        </div>
      ) : null}
      <div className="relative">
        <div
          aria-hidden="true"
          data-mobile-slot-rail
          className="pointer-events-none absolute inset-y-0 left-1/2 z-0 w-11 -translate-x-1/2 border-x border-[#101d31] bg-[#060c17]"
        />
        {Array.from({ length: rowCount }, (_, index) => {
          const myPlayer = myPlayers[index];
          const opponentPlayer = opponentPlayers[index];
          const slot = compactSlot(myPlayer ?? opponentPlayer);
          const hasFollowingRow = index < rowCount - 1;
          return (
            <div
              key={`${slot}-${index}`}
              data-mobile-matchup-row
              className="relative z-10 grid min-h-[72px] grid-cols-[minmax(0,1fr)_2.75rem_minmax(0,1fr)] items-stretch px-3"
            >
              <div className={`flex min-w-0 items-center py-2 ${hasFollowingRow ? "border-b-2 border-[#07101f]" : ""}`}>
                <CompactMatchupPlayer player={myPlayer} align="left" onSelect={onPlayerSelect} />
              </div>
              <span data-mobile-slot-column className="inline-flex min-h-[72px] items-center justify-center px-1 text-[9px] font-black uppercase tracking-[0.04em] text-cfb-text-secondary">
                {slot}
              </span>
              <div className={`flex min-w-0 items-center py-2 ${hasFollowingRow ? "border-b-2 border-[#07101f]" : ""}`}>
                <CompactMatchupPlayer player={opponentPlayer} align="right" onSelect={onPlayerSelect} />
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
}: {
  myTeam: LeagueMatchupTeam | null;
  opponentTeam: LeagueMatchupTeam | null;
  leagueId?: number | string;
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

  return (
    <div className="space-y-4 sm:space-y-6">
      <section className="space-y-3">
        <CompactMobileLineup
          title="Starter matchup"
          myPlayers={myStarters}
          opponentPlayers={opponentStarters}
          testId="mobile-starting-lineup"
          showHeader={false}
          onPlayerSelect={setSelectedPlayer}
        />
        <div className="hidden gap-5 md:grid xl:grid-cols-2">
          <RosterSlotTable
            title={myTeam?.fantasy_team_name || "Your Starters"}
            players={myStarters}
            emptyText="Your starters are empty or projections are unavailable."
            showPositionColumn={false}
            leagueId={leagueId}
          />
          <RosterSlotTable
            title={opponentTeam?.fantasy_team_name || "Opponent Starters"}
            players={opponentStarters}
            emptyText="Opponent starters are pending."
            showPositionColumn={false}
            leagueId={leagueId}
          />
        </div>
      </section>

      <details className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/95 p-0 md:hidden">
        <summary className="flex min-h-[52px] cursor-pointer list-none items-center justify-between px-4 text-[11px] font-black uppercase tracking-[0.16em] text-cfb-text-secondary [&::-webkit-details-marker]:hidden">
          Bench depth
          <span className="text-[9px] text-cfb-text-muted">{myReserves.length} / {opponentReserves.length}</span>
        </summary>
        <div className="border-t border-cfb-border-subtle p-3">
          <CompactMobileLineup
            title="Bench"
            myPlayers={myReserves}
            opponentPlayers={opponentReserves}
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
        <div className="grid gap-5 xl:grid-cols-2">
          <RosterSlotTable
            title={`${myTeam?.fantasy_team_name || "Your Team"} Bench`}
            players={myReserves}
            emptyText="Your bench is empty."
            showPositionColumn={false}
            tone="bench"
            leagueId={leagueId}
          />
          <RosterSlotTable
            title={`${opponentTeam?.fantasy_team_name || "Opponent"} Bench`}
            players={opponentReserves}
            emptyText="Opponent bench is pending."
            showPositionColumn={false}
            tone="bench"
            leagueId={leagueId}
          />
        </div>
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
