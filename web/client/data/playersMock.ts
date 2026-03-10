import { Player } from "@/types/player";

export const allPlayersMock: Player[] = [
  {
    id: 1,
    name: "Quinn Ewers",
    school: "TEXAS",
    pos: "QB",
    conf: "SEC",
    rank: 1,
    adp: 1.2,
    posRank: 1,
    rostered: 99.8,
    status: "HEALTHY",
    number: 3,
    projection: { passingYards: 3450.0, passingTds: 28.0, ints: 8.0, fpts: 345.5, qbr: 78.5, expectedPlays: 44.8, expectedRushPerPlay: 0.09, expectedTdPerPlay: 0.06, floor: 22.4, ceiling: 38.6, boomProb: 0.24, bustProb: 0.12 },
    history: [
      { year: 2025, stats: { passingYards: 3120, passingTds: 22, ints: 6, fpts: 310.4, qbr: 75.2, rushingYards: 120, rushingTds: 2 } },
      { year: 2024, stats: { passingYards: 2800, passingTds: 18, ints: 8, fpts: 275.2, qbr: 70.8, rushingYards: 85, rushingTds: 1 } }
    ],
    analysis: "Expected to lead one of the most explosive offenses in the SEC. His mobility and deep-ball accuracy make him a top-tier fantasy asset in all formats."
  },
  {
    id: 2,
    name: "Ollie Gordon II",
    school: "OKST",
    pos: "RB",
    conf: "Big 12",
    rank: 2,
    adp: 2.5,
    posRank: 1,
    rostered: 99.7,
    status: "HEALTHY",
    number: 0,
    projection: { rushingYards: 1650.0, rushingTds: 18.0, receptions: 45, receivingYards: 320, receivingTds: 2.0, fpts: 325.2, expectedPlays: 24.6, expectedRushPerPlay: 0.18, expectedTdPerPlay: 0.05, floor: 15.8, ceiling: 32.4, boomProb: 0.28, bustProb: 0.10 },
    history: [
      { year: 2025, stats: { rushingYards: 1580, rushingTds: 16, receptions: 38, receivingYards: 280, receivingTds: 1, fpts: 305.8 } }
    ],
    analysis: "The centerpiece of the Oklahoma State offense. His workload is unparalleled among CFB running backs, making him a volume-based monster."
  },
  {
    id: 3,
    name: "Luther Burden III",
    school: "MISSOURI",
    pos: "WR",
    conf: "SEC",
    rank: 3,
    adp: 3.8,
    posRank: 1,
    rostered: 99.5,
    status: "HEALTHY",
    number: 3,
    projection: { receptions: 95, receivingYards: 1350.0, receivingTds: 12.0, fpts: 302.5, expectedPlays: 12.8, expectedRushPerPlay: 0.00, expectedTdPerPlay: 0.06, floor: 13.4, ceiling: 28.2, boomProb: 0.22, bustProb: 0.14 },
    history: [
      { year: 2025, stats: { receptions: 86, receivingYards: 1210, receivingTds: 9, fpts: 261.2 } }
    ],
    analysis: "A dynamic threat in space who excels in YAC. His connection with his QB makes him the most reliable WR option in the country."
  },
  {
    id: 4,
    name: "Dillon Gabriel",
    school: "OREGON",
    pos: "QB",
    conf: "Big Ten",
    rank: 4,
    adp: 4.1,
    posRank: 2,
    rostered: 99.2,
    status: "HEALTHY",
    number: 8,
    projection: { passingYards: 3800.0, passingTds: 32.0, ints: 7.0, fpts: 385.0, qbr: 82.4, expectedPlays: 46.2, expectedRushPerPlay: 0.10, expectedTdPerPlay: 0.07, floor: 24.6, ceiling: 41.0, boomProb: 0.26, bustProb: 0.11 },
    history: [
      { year: 2025, stats: { passingYards: 3660, passingTds: 30, ints: 6, fpts: 368.5, qbr: 80.1, rushingYards: 450, rushingTds: 6 } }
    ],
    analysis: "Transferring to the Ducks puts him in a system perfectly suited for his dual-threat capabilities. Expect massive numbers in the Big Ten."
  },
  {
    id: 5,
    name: "Tyleik Williams",
    school: "OSU",
    pos: "DL",
    conf: "Big Ten",
    rank: 5,
    adp: 12.5,
    posRank: 1,
    rostered: 85.2,
    status: "HEALTHY",
    number: 91,
    projection: { fpts: 145.2, expectedPlays: 0, expectedRushPerPlay: 0, expectedTdPerPlay: 0, floor: 6.8, ceiling: 18.4, boomProb: 0.12, bustProb: 0.22 },
    history: [
      { year: 2025, stats: { fpts: 132.5 } }
    ],
    analysis: "A force in the interior line. While IDP scoring varies, his consistency in recording TFLs and pressures makes him the top DL prospect."
  },
  {
    id: 6,
    name: "TreVeyon Henderson",
    school: "OSU",
    pos: "RB",
    conf: "Big Ten",
    rank: 6,
    adp: 6.8,
    posRank: 2,
    rostered: 98.8,
    status: "HEALTHY",
    number: 32,
    projection: { rushingYards: 1250.0, rushingTds: 14.0, receptions: 25, fpts: 245.8, expectedPlays: 18.4, expectedRushPerPlay: 0.16, expectedTdPerPlay: 0.04, floor: 12.0, ceiling: 26.2, boomProb: 0.20, bustProb: 0.15 },
    history: [
      { year: 2025, stats: { rushingYards: 1150, rushingTds: 11, receptions: 20, fpts: 215.2 } }
    ],
    analysis: "Splitting carries might limit his ceiling, but his efficiency and home-run threat on every touch keep him in the elite tier."
  },
  {
    id: 7,
    name: "Tetairoa McMillan",
    school: "ARIZONA",
    pos: "WR",
    conf: "Big 12",
    rank: 7,
    adp: 7.2,
    posRank: 2,
    rostered: 98.5,
    status: "HEALTHY",
    number: 4,
    projection: { receptions: 88, receivingYards: 1280.0, receivingTds: 11.0, fpts: 282.4, expectedPlays: 12.2, expectedRushPerPlay: 0.00, expectedTdPerPlay: 0.06, floor: 12.8, ceiling: 27.6, boomProb: 0.21, bustProb: 0.13 },
    history: [
      { year: 2025, stats: { receptions: 80, receivingYards: 1150, receivingTds: 10, fpts: 255.0 } }
    ],
    analysis: "An absolute catch-radius monster. His ability to win contested balls makes him a red-zone favorite for his quarterback."
  }
];
