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

const compactPlayerMeta = (player?: LeagueRosterPlayer) => {
  if (!player?.player_id) return "Open slot";
  const school = player.school ?? player.player_school ?? "School TBD";
  const opponent = player.opponent ? `vs ${player.opponent}` : "Opponent TBD";
  return `${school} · ${opponent}`;
};

function CompactMatchupPlayer({ player, align }: { player?: LeagueRosterPlayer; align: "left" | "right" }) {
  const hasPlayer = Boolean(player?.player_id && player.player_name);
  return (
    <div className={`min-w-0 ${align === "right" ? "text-right" : "text-left"}`}>
      <p className={`truncate text-[12px] font-black leading-4 text-cfb-text-primary ${hasPlayer ? "" : "text-cfb-text-muted"}`}>
        {hasPlayer ? player?.player_name : "Open slot"}
      </p>
      <p className="mt-0.5 truncate text-[9px] font-bold leading-3 text-cfb-text-muted">
        {compactPlayerMeta(player)}
      </p>
      <p className={`mt-1 text-[11px] font-black tabular-nums ${align === "right" ? "text-cfb-pink" : "text-cfb-brand"}`}>
        {compactProjection(player)} <span className="text-[8px] uppercase tracking-[0.08em] text-cfb-text-muted">proj</span>
      </p>
    </div>
  );
}

function CompactMobileLineup({
  title,
  myPlayers,
  opponentPlayers,
  testId,
}: {
  title: string;
  myPlayers: LeagueRosterPlayer[];
  opponentPlayers: LeagueRosterPlayer[];
  testId: string;
}) {
  const rowCount = Math.max(myPlayers.length, opponentPlayers.length);

  return (
    <section data-testid={testId} className="overflow-hidden rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/95 shadow-[0_16px_38px_rgba(2,6,23,0.26)] md:hidden">
      <div className="flex items-center justify-between border-b border-cfb-border-subtle bg-cfb-surface/70 px-4 py-3">
        <h2 className="text-[11px] font-black uppercase tracking-[0.17em] text-cfb-brand">{title}</h2>
        <span className="text-[9px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">Weekly proj</span>
      </div>
      <div className="divide-y divide-cfb-border-subtle/80">
        {Array.from({ length: rowCount }, (_, index) => {
          const myPlayer = myPlayers[index];
          const opponentPlayer = opponentPlayers[index];
          const slot = compactSlot(myPlayer ?? opponentPlayer);
          return (
            <div
              key={`${slot}-${index}`}
              data-mobile-matchup-row
              className="grid min-h-[74px] grid-cols-[minmax(0,1fr)_2.7rem_minmax(0,1fr)] items-center gap-2 px-3 py-2.5"
            >
              <CompactMatchupPlayer player={myPlayer} align="left" />
              <span className="inline-flex min-h-8 items-center justify-center rounded-full border border-cfb-brand/35 bg-cfb-brand/[0.08] px-1 text-[9px] font-black uppercase tracking-[0.04em] text-cfb-text-secondary">
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
        <div>
          <p className="cfb-micro-label text-cfb-brand">
            Starting Matchup
          </p>
        </div>
        <CompactMobileLineup
          title="Starting lineup"
          myPlayers={myStarters}
          opponentPlayers={opponentStarters}
          testId="mobile-starting-lineup"
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
