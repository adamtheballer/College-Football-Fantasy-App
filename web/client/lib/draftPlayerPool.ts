import { Player } from "@/types/player";
import { secDepthCharts } from "@/data/sec_depth_charts";
import { applyInjuryRedistribution } from "@/lib/injuryAdjustments";

const GAMES_IN_SEASON = 12;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const buildSeasonProjection = (pos: string, depth: number) => {
  const perGameBase = () => {
    if (pos === "QB") return clamp(24 - (depth - 1) * 6, 8, 30);
    if (pos === "RB") return clamp(18 - (depth - 1) * 5, 5, 26);
    if (pos === "WR") return clamp(17 - (depth - 1) * 4, 5, 24);
    if (pos === "TE") return clamp(13 - (depth - 1) * 4, 4, 20);
    return clamp(8 - (depth - 1) * 2, 3, 12);
  };

  const fptsPerGame = perGameBase();
  const fpts = fptsPerGame * GAMES_IN_SEASON;

  if (pos === "QB") {
    return {
      passingYards: fptsPerGame * 12 * GAMES_IN_SEASON,
      passingTds: (fptsPerGame / 12) * GAMES_IN_SEASON,
      ints: 0.8 * GAMES_IN_SEASON,
      rushingYards: 18 * GAMES_IN_SEASON,
      rushingTds: 1.5,
      fpts,
      expectedPlays: 42,
      expectedRushPerPlay: 0.08,
      expectedTdPerPlay: 0.06,
      floor: fptsPerGame * 0.7,
      ceiling: fptsPerGame * 1.3,
      boomProb: 0.22,
      bustProb: 0.14,
      qbr: 70 + (depth === 1 ? 8 : 0),
    };
  }
  if (pos === "RB") {
    return {
      rushingYards: fptsPerGame * 5 * GAMES_IN_SEASON,
      rushingTds: (fptsPerGame / 16) * GAMES_IN_SEASON,
      receptions: 2.5 * GAMES_IN_SEASON,
      receivingYards: fptsPerGame * 1.5 * GAMES_IN_SEASON,
      receivingTds: (fptsPerGame / 60) * GAMES_IN_SEASON,
      fpts,
      expectedPlays: 18,
      expectedRushPerPlay: 0.18,
      expectedTdPerPlay: 0.05,
      floor: fptsPerGame * 0.7,
      ceiling: fptsPerGame * 1.3,
      boomProb: 0.2,
      bustProb: 0.16,
    };
  }
  if (pos === "WR" || pos === "TE") {
    return {
      receptions: (pos === "TE" ? 3.5 : 5.0) * GAMES_IN_SEASON,
      receivingYards: fptsPerGame * 7 * GAMES_IN_SEASON,
      receivingTds: (fptsPerGame / 24) * GAMES_IN_SEASON,
      fpts,
      expectedPlays: 10,
      expectedRushPerPlay: 0.0,
      expectedTdPerPlay: 0.05,
      floor: fptsPerGame * 0.7,
      ceiling: fptsPerGame * 1.3,
      boomProb: 0.18,
      bustProb: 0.18,
    };
  }
  return {
    fpts,
    expectedPlays: 0,
    expectedRushPerPlay: 0,
    expectedTdPerPlay: 0,
    floor: fptsPerGame * 0.7,
    ceiling: fptsPerGame * 1.3,
    boomProb: 0.12,
    bustProb: 0.22,
  };
};

const buildSecDepthChartPlayers = (startId: number) => {
  const players: Player[] = [];
  const posCounts: Record<string, number> = {};
  let idCounter = startId;

  secDepthCharts.forEach((team) => {
    const positions = team.positions as Record<string, { depth: number; name: string; classYear: string }[]>;
    Object.entries(positions).forEach(([pos, depthPlayers]) => {
      depthPlayers.forEach((depthPlayer) => {
        if (!depthPlayer.name || depthPlayer.name.toLowerCase() === "not sure") {
          return;
        }
        const posKey = pos.toUpperCase();
        posCounts[posKey] = (posCounts[posKey] || 0) + 1;
        const projection = buildSeasonProjection(posKey, depthPlayer.depth);
        players.push({
          id: idCounter,
          name: depthPlayer.name,
          school: team.team.toUpperCase(),
          pos: posKey,
          conf: "SEC",
          rank: idCounter,
          adp: 0,
          posRank: posCounts[posKey],
          rostered: 0,
          status: "HEALTHY",
          projection,
          history: [],
          analysis: `${posKey} preseason projection from depth chart.`,
        });
        idCounter += 1;
      });
    });
  });

  return players;
};

export const buildDraftPlayerPool = (basePlayers: Player[]) => {
  const maxId = basePlayers.reduce((max, p) => Math.max(max, p.id), 0);
  const secPlayers = buildSecDepthChartPlayers(maxId + 1);
  const combined = [...basePlayers, ...secPlayers];
  const seen = new Map<string, Player>();
  combined.forEach((player) => {
    const key = `${player.name}-${player.school}-${player.pos}`;
    if (!seen.has(key)) {
      seen.set(key, player);
    }
  });
  return applyInjuryRedistribution(Array.from(seen.values()));
};
