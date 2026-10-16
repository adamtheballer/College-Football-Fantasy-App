import type {
  Challenge,
  ChallengeKind,
  Pick,
} from "@/hooks/use-weekly-challenges";

// Matches the five published formats and the API's authoritative entry rules.
export const CHALLENGE_PICK_COUNTS: Record<ChallengeKind, number> = {
  slate12: 12,
  upset: 3,
  fantasy5: 5,
  lock: 1,
  duels: 5,
};
export const FANTASY_SLOTS = ["QB", "RB", "WR", "TE", "FLEX"] as const;

/** One preflight for buttons, keyboard submit and recovered drafts. The API still validates every write. */
export function challengeEntryError(
  c: Challenge,
  picks: Pick[],
  tiebreaker: string,
  complete: boolean,
): string | null {
  const count = CHALLENGE_PICK_COUNTS[c.kind];
  if (picks.length > count || (complete && picks.length !== count))
    return `Choose exactly ${count} ${c.kind === "fantasy5" ? "players" : "picks"} before submitting.`;
  if (picks.some((p) => !p || typeof p !== "object"))
    return "Remove invalid selections and choose again.";
  if (c.kind === "fantasy5") {
    const players = new Map(c.players.map((p) => [p.id, p]));
    if (
      new Set(picks.map((p) => p.player_id)).size !== picks.length ||
      new Set(picks.map((p) => p.slot)).size !== picks.length
    )
      return "Choose distinct players and lineup slots.";
    if (
      picks.some((p) => {
        const player = players.get(p.player_id!);
        return (
          !player ||
          !FANTASY_SLOTS.includes(p.slot!) ||
          p.game_id !== undefined ||
          p.team !== undefined ||
          (p.slot === "FLEX"
            ? !["RB", "WR", "TE"].includes(player.position)
            : player.position !== p.slot)
        );
      })
    )
      return "Choose an eligible published player for each lineup slot.";
  } else {
    if (new Set(picks.map((p) => p.game_id)).size !== picks.length)
      return "Each pick must use a different game.";
    const games = new Map(c.games.map((g) => [g.id, g]));
    if (
      picks.some((p) => {
        const game = games.get(p.game_id!);
        return (
          !game ||
          p.player_id !== undefined ||
          p.slot !== undefined ||
          ![game.home_team, game.away_team].includes(p.team!)
        );
      })
    )
      return "Choose a published team in its own game.";
    if (
      c.kind === "upset" &&
      picks.some(
        (p) =>
          !c.underdogs.some(
            (d) => d.game_id === p.game_id && d.team === p.team,
          ),
      )
    )
      return "Only published underdogs are eligible.";
  }
  if (c.kind === "slate12") {
    if (tiebreaker === "")
      return complete
        ? "Predict the featured game's combined final score."
        : null;
    const total = Number(tiebreaker);
    if (!Number.isInteger(total) || total < 0 || total > 2_147_483_647)
      return "Enter a whole-number score prediction from 0 to 2147483647.";
  } else if (tiebreaker !== "") return "This format has no tiebreaker.";
  return null;
}
