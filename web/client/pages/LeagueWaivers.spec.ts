import { describe, expect, it } from "vitest";

import { buildWaiverClaimPayload, canSubmitWaiverClaim, claimStatusLabel } from "./LeagueWaivers";

describe("LeagueWaivers claim helpers", () => {
  it("blocks claim submission before the draft or without a selected player", () => {
    expect(canSubmitWaiverClaim({ teamId: 4, addPlayerId: 9 }, true)).toBe(false);
    expect(canSubmitWaiverClaim({ teamId: 4, addPlayerId: null }, false)).toBe(false);
    expect(canSubmitWaiverClaim({ teamId: 4, addPlayerId: 9 }, false)).toBe(true);
  });

  it("builds a FAAB add/drop waiver claim payload", () => {
    expect(
      buildWaiverClaimPayload({
        teamId: 4,
        addPlayerId: 9,
        dropPlayerId: 12,
        bidAmount: "17",
        waiverType: "faab",
      })
    ).toEqual({
      team_id: 4,
      add_player_id: 9,
      drop_player_id: 12,
      bid_amount: 17,
    });
  });

  it("zeroes non-FAAB bids and labels failed claims with the audit reason", () => {
    expect(buildWaiverClaimPayload({ teamId: 4, addPlayerId: 9, bidAmount: "20", waiverType: "rolling" })).toMatchObject({
      bid_amount: 0,
      drop_player_id: null,
    });
    expect(claimStatusLabel({ status: "failed", failure_reason: "player is no longer available" })).toBe(
      "Failed · player is no longer available"
    );
  });

  it("requires a real team and player id", () => {
    expect(() => buildWaiverClaimPayload({ teamId: null, addPlayerId: 9 })).toThrow("Choose a player");
    expect(() => buildWaiverClaimPayload({ teamId: 4, addPlayerId: null })).toThrow("Choose a player");
  });
});
