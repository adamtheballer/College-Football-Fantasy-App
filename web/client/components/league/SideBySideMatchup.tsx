import { RosterSlotTable } from "@/components/league/RosterSlotTable";
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

export function SideBySideMatchup({
  myTeam,
  opponentTeam,
  leagueId,
}: {
  myTeam: LeagueMatchupTeam | null;
  opponentTeam: LeagueMatchupTeam | null;
  leagueId?: number | string;
}) {
  const myStarters = startersFor(myTeam);
  const opponentStarters = startersFor(opponentTeam);
  const myReserves = reservesFor(myTeam);
  const opponentReserves = reservesFor(opponentTeam);

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">
            Starting Matchup
          </p>
        </div>
        <div className="grid gap-5 xl:grid-cols-2">
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

      <section className="space-y-3 rounded-[1.75rem] border border-white/10 bg-slate-950/25 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">
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
      </section>
    </div>
  );
}
