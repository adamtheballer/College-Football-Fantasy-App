export type CreateLeagueScoring = {
  ppr: number;
  pass_td: number;
  pass_yds_per_pt: number;
  rush_yds_per_pt: number;
  rec_yds_per_pt: number;
  rush_td: number;
  rec_td: number;
  int: number;
  fumble_lost: number;
  fg: number;
  xp: number;
};

const numberOr = (value: unknown, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const yardsPerPointToMultiplier = (value: unknown, fallback: number) => {
  const yardsPerPoint = numberOr(value, fallback);
  if (yardsPerPoint <= 0) {
    return 0;
  }
  return Number((1 / yardsPerPoint).toFixed(6));
};

const fieldGoalTierPoints = (value: unknown) => {
  const base = numberOr(value, 3);
  return {
    fg_made_0_30: base,
    fg_made_31_40: base,
    fg_made_41_50: base + 1,
    fg_made_51_60: base + 2,
    fg_made_61_plus: base + 2,
    fg_missed: 0,
  };
};

export const createLeagueScoringToApi = (scoring: CreateLeagueScoring) => ({
  receptions: numberOr(scoring.ppr, 1),
  pass_tds: numberOr(scoring.pass_td, 4),
  pass_yards: yardsPerPointToMultiplier(scoring.pass_yds_per_pt, 25),
  rush_yards: yardsPerPointToMultiplier(scoring.rush_yds_per_pt, 10),
  rec_yards: yardsPerPointToMultiplier(scoring.rec_yds_per_pt, 10),
  rush_tds: numberOr(scoring.rush_td, 6),
  rec_tds: numberOr(scoring.rec_td, 6),
  interceptions: numberOr(scoring.int, -2),
  fumbles_lost: numberOr(scoring.fumble_lost, -2),
  ...fieldGoalTierPoints(scoring.fg),
  xp_made: numberOr(scoring.xp, 1),
});
