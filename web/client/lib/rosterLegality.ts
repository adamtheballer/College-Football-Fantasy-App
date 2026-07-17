export type RosterSlotKey =
  | "QB"
  | "RB"
  | "WR"
  | "TE"
  | "FLEX"
  | "SUPERFLEX"
  | "K"
  | "BENCH";

export type PlayerPosition = "QB" | "RB" | "WR" | "TE" | "K";

export type RosterSlotLimits = Record<string, number>;

export type RosterPlayer = {
  id: number;
  position: string;
  assignedSlot?: string | null;
};

export type DraftablePlayer = {
  id: number;
  position?: string | null;
  pos?: string | null;
};

export type RosterLegalityOptions = {
  superflexEnabled?: boolean;
};

const PLAYER_POSITIONS = new Set<PlayerPosition>(["QB", "RB", "WR", "TE", "K"]);
const SLOT_KEYS = new Set<RosterSlotKey>([
  "QB",
  "RB",
  "WR",
  "TE",
  "FLEX",
  "SUPERFLEX",
  "K",
  "BENCH",
]);

export const normalizePosition = (position: string | null | undefined): PlayerPosition | null => {
  const normalized = position?.trim().toUpperCase();
  return normalized && PLAYER_POSITIONS.has(normalized as PlayerPosition)
    ? (normalized as PlayerPosition)
    : null;
};

const normalizeSlotKey = (slot: string | null | undefined): RosterSlotKey | null => {
  const normalized = slot?.trim().toUpperCase();
  if (!normalized) return null;
  if (normalized === "BE") return "BENCH";
  if (normalized.startsWith("BENCH")) return "BENCH";
  if (normalized.startsWith("RB ")) return "RB";
  if (normalized.startsWith("WR ")) return "WR";
  return SLOT_KEYS.has(normalized as RosterSlotKey) ? (normalized as RosterSlotKey) : null;
};

const normalizeRosterSlotLimits = (rosterSlotLimits: RosterSlotLimits): Record<RosterSlotKey, number> => ({
  QB: Number(rosterSlotLimits.QB ?? 0),
  RB: Number(rosterSlotLimits.RB ?? 0),
  WR: Number(rosterSlotLimits.WR ?? 0),
  TE: Number(rosterSlotLimits.TE ?? 0),
  FLEX: Number(rosterSlotLimits.FLEX ?? 0),
  SUPERFLEX: Number(rosterSlotLimits.SUPERFLEX ?? 0),
  K: Number(rosterSlotLimits.K ?? 0),
  BENCH: Number(rosterSlotLimits.BENCH ?? rosterSlotLimits.BE ?? 0),
});

export const getEligibleSlotsForPosition = (
  position: PlayerPosition,
  superflexEnabled = false
): RosterSlotKey[] => {
  if (position === "QB") {
    return superflexEnabled ? ["QB", "SUPERFLEX", "BENCH"] : ["QB", "BENCH"];
  }
  if (position === "RB" || position === "WR" || position === "TE") {
    return [position, "FLEX", "BENCH"];
  }
  return ["K", "BENCH"];
};

const assignFromCounts = (
  position: PlayerPosition,
  counts: Partial<Record<RosterSlotKey, number>>,
  limits: Record<RosterSlotKey, number>,
  options: RosterLegalityOptions = {}
): RosterSlotKey | null => {
  const eligibleSlots = getEligibleSlotsForPosition(
    position,
    Boolean(options.superflexEnabled) || Number(limits.SUPERFLEX ?? 0) > 0
  );
  for (const slot of eligibleSlots) {
    if ((limits[slot] ?? 0) > (counts[slot] ?? 0)) {
      return slot;
    }
  }
  return null;
};

export const countRosterSlots = (
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits = {},
  options: RosterLegalityOptions = {}
): Record<string, number> => {
  const limits = normalizeRosterSlotLimits(rosterSlotLimits);
  const counts: Partial<Record<RosterSlotKey, number>> = {};

  for (const player of rosterPlayers) {
    const assignedSlot = normalizeSlotKey(player.assignedSlot);
    const position = normalizePosition(player.position);
    const slot = assignedSlot ?? (position ? assignFromCounts(position, counts, limits, options) : null);
    if (!slot) continue;
    counts[slot] = (counts[slot] ?? 0) + 1;
  }

  return counts;
};

export const getOpenSlots = (
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits,
  options: RosterLegalityOptions = {}
): Record<string, number> => {
  const limits = normalizeRosterSlotLimits(rosterSlotLimits);
  const counts = countRosterSlots(rosterPlayers, rosterSlotLimits, options);
  return Object.fromEntries(
    Object.entries(limits).map(([slot, limit]) => [
      slot,
      Math.max(0, Number(limit || 0) - Number(counts[slot] || 0)),
    ])
  );
};

export const canPositionFitRoster = (
  position: string | null | undefined,
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits,
  options: RosterLegalityOptions = {}
) => assignBestRosterSlotForPosition(position, rosterPlayers, rosterSlotLimits, options) !== null;

export const getLegalPositionsForRoster = (
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits,
  options: RosterLegalityOptions = {}
): PlayerPosition[] =>
  (["QB", "RB", "WR", "TE", "K"] as PlayerPosition[]).filter((position) =>
    canPositionFitRoster(position, rosterPlayers, rosterSlotLimits, options)
  );

export const filterDraftablePlayers = <TPlayer extends DraftablePlayer>(
  players: TPlayer[],
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits,
  draftedPlayerIds: Set<number>,
  options: RosterLegalityOptions = {}
): TPlayer[] =>
  players.filter((player) => {
    if (draftedPlayerIds.has(player.id)) return false;
    const position = normalizePosition(player.position ?? player.pos);
    if (!position) return false;
    return canPositionFitRoster(position, rosterPlayers, rosterSlotLimits, options);
  });

export const assignBestRosterSlotForPosition = (
  position: string | null | undefined,
  rosterPlayers: RosterPlayer[],
  rosterSlotLimits: RosterSlotLimits,
  options: RosterLegalityOptions = {}
): RosterSlotKey | null => {
  const normalizedPosition = normalizePosition(position);
  if (!normalizedPosition) return null;
  const limits = normalizeRosterSlotLimits(rosterSlotLimits);
  const counts = countRosterSlots(rosterPlayers, rosterSlotLimits, options);
  return assignFromCounts(normalizedPosition, counts, limits, options);
};
