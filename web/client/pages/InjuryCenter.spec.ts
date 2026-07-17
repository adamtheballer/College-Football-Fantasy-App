import { describe, expect, it } from "vitest";

import { buildInjuryPlayerCard } from "./InjuryCenter";

describe("buildInjuryPlayerCard", () => {
  it("maps an injury row into the canonical player card contract", () => {
    expect(
      buildInjuryPlayerCard({
        id: 42,
        name: "Runner One",
        team: "Texas",
        conference: "SEC",
        pos: "RB",
        status: "QUESTIONABLE",
        injury: "Ankle",
        returnTimeline: "Game-time decision",
        projectionDelta: -2.5,
        lastUpdated: "Updated recently",
      }),
    ).toEqual({
      id: 42,
      name: "Runner One",
      school: "Texas",
      position: "RB",
      status: "QUESTIONABLE",
    });
  });
});
