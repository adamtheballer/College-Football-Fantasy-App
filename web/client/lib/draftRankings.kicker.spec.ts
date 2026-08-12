import { describe, expect, it } from "vitest";

import { getEarliestKickerDraftRank } from "./draftRankings";

const standardRosterSlots = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  K: 1,
  BE: 5,
  IR: 1,
};

describe("kicker draft-board placement", () => {
  it("never promotes kickers into the early board for a small league", () => {
    expect(
      getEarliestKickerDraftRank({
        leagueSize: 4,
        rosterSlots: standardRosterSlots,
      }),
    ).toBe(100);
  });

  it("still keeps kickers in the final rounds for a standard twelve-team league", () => {
    expect(
      getEarliestKickerDraftRank({
        leagueSize: 12,
        rosterSlots: standardRosterSlots,
      }),
    ).toBe(132);
  });
});
