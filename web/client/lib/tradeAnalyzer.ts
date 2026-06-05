export type TradePlayer = {
  id: number;
  name: string;
  pos: string;
  school: string;
  fpts: number;
  posRank: number;
  status?: string;
};

const positionScarcity: Record<string, number> = {
  QB: 0.85,
  RB: 1.12,
  WR: 1.08,
  TE: 1.05,
  K: 0.6,
};

// Schedule adjustments are now sourced from backend comparison endpoints.
// Keep neutral weighting in this utility to avoid synthetic client-only matchup data.
const scheduleModifier = () => 1;

const injuryPenalty = (status?: string) => {
  if (!status) return 1;
  const normalized = status.toUpperCase();
  if (normalized === "OUT") return 0.75;
  if (normalized === "DOUBTFUL") return 0.85;
  if (normalized === "QUESTIONABLE") return 0.92;
  return 0.98;
};

export const computeBasicTradeValue = (player: TradePlayer) => {
  const scarcity = positionScarcity[player.pos] ?? 1;
  const schedule = scheduleModifier();
  const injury = injuryPenalty(player.status);
  const positionRank = Number.isFinite(player.posRank) ? player.posRank : 12;
  const rankBoost = 1 + Math.max(0, (12 - positionRank)) * 0.01;
  const value = player.fpts * scarcity * schedule * injury * rankBoost;
  return Number(value.toFixed(1));
};

export const computeTradeValue = computeBasicTradeValue;

export const evaluateBasicTrade = (receive: TradePlayer[], give: TradePlayer[]) => {
  const receiveValue = receive.reduce((sum, p) => sum + computeBasicTradeValue(p), 0);
  const giveValue = give.reduce((sum, p) => sum + computeBasicTradeValue(p), 0);
  const delta = receiveValue - giveValue;
  const deltaPct = giveValue === 0 ? 0 : delta / giveValue;

  let verdict = "Basic Even";
  if (deltaPct >= 0.08) verdict = "Basic Lean Receive";
  else if (deltaPct >= 0.03) verdict = "Basic Slight Edge";
  else if (deltaPct <= -0.08) verdict = "Basic Lean Give";
  else if (deltaPct <= -0.03) verdict = "Basic Slight Loss";

  return {
    receiveValue: Number(receiveValue.toFixed(1)),
    giveValue: Number(giveValue.toFixed(1)),
    delta: Number(delta.toFixed(1)),
    verdict,
  };
};

export const evaluateTrade = evaluateBasicTrade;
