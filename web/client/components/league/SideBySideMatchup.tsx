import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { SurfaceCard } from "@/components/fantasy";
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
  return new Intl.DateTimeFormat(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" }).format(kickoff);
};

export const formatPlayerGameContext = (player?: LeagueRosterPlayer) => {
  if (!player?.player_id) return "Open slot";
  const school = player.school ?? player.player_school ?? "School TBD";
  if (!player.opponent) return `${school} · ${kickoffLabel(player.game_start_at)}`;

  // The API supplies the player's team's venue. Keep the road team first in the
  // compact matchup notation so it reads consistently across the app.
  const matchup = player.game_location === "home"
    ? `${player.opponent} @ ${school}`
    : player.game_location === "neutral"
      ? `${school} vs ${player.opponent} · Neutral`
      : `${school} @ ${player.opponent}`;
  return `${matchup} · ${kickoffLabel(player.game_start_at)}`;
};

function CompactMatchupPlayer({ player, align }: { player?: LeagueRosterPlayer; align: "left" | "right" }) {
  const hasPlayer = Boolean(player?.player_id && player.player_name);
  const points = compactProjection(player);
  return (
    <div className={`min-w-0 ${align === "right" ? "text-right" : "text-left"}`}>
      <div className={`flex min-w-0 items-baseline gap-1.5 ${align === "right" ? "justify-end" : "justify-start"}`}>
        {align === "right" ? (
          <p className="shrink-0 text-[11px] font-black tabular-nums text-cfb-pink">
            {points}
          </p>
        ) : null}
        <p className={`min-w-0 truncate text-[12px] font-black leading-4 text-cfb-text-primary ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
          {hasPlayer ? compactMatchupPlayerName(player?.player_name) : "No starter set"}
        </p>
        {align === "left" ? (
          <p className="shrink-0 text-[11px] font-black tabular-nums text-cfb-brand">
            {points}
          </p>
        ) : null}
      </div>
      <p className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
        {hasPlayer ? formatPlayerGameContext(player) : "Set a starter in your roster"}
      </p>
    </div>
  );
}

function CompactMobileLineup({
  title,
  myPlayers,
  opponentPlayers,
  testId,
  showHeader = true,
}: {
  title: string;
  myPlayers: LeagueRosterPlayer[];
  opponentPlayers: LeagueRosterPlayer[];
  testId: string;
  showHeader?: boolean;
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
      <div>
        {Array.from({ length: rowCount }, (_, index) => {
          const myPlayer = myPlayers[index];
          const opponentPlayer = opponentPlayers[index];
          const slot = compactSlot(myPlayer ?? opponentPlayer);
          return (
            <div
              key={`${slot}-${index}`}
              data-mobile-matchup-row
              className="grid min-h-[64px] grid-cols-[minmax(0,1fr)_2.75rem_minmax(0,1fr)] items-center border-b-2 border-[#07101f] px-3 py-2 last:border-b-0"
            >
              <CompactMatchupPlayer player={myPlayer} align="left" />
              <span data-mobile-slot-column className="inline-flex min-h-[64px] self-stretch items-center justify-center border-x border-[#101d31] bg-[#060c17] px-1 text-[9px] font-black uppercase tracking-[0.04em] text-cfb-text-secondary">
                {slot}
              </span>
              <CompactMatchupPlayer player={opponentPlayer} align="right" />
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
  const myStarters = sortBySlot(startersFor(myTeam));
  const opponentStarters = sortBySlot(startersFor(opponentTeam));
  const myReserves = sortBySlot(reservesFor(myTeam));
  const opponentReserves = sortBySlot(reservesFor(opponentTeam));

  return (
    <div className="space-y-4 sm:space-y-6">
      <section className="space-y-3">
        <CompactMobileLineup
          title="Starter matchup"
          myPlayers={myStarters}
          opponentPlayers={opponentStarters}
          testId="mobile-starting-lineup"
          showHeader={false}
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
    </div>
  );
}
