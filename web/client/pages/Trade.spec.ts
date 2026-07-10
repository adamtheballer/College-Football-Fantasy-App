import { describe, expect, it } from "vitest";

import { buildTradeOfferPayload, canSubmitTradeOffer, tradeStatusLabel } from "./Trade";

describe("Trade offer helpers", () => {
  it("requires two different teams and at least one player on each side", () => {
    expect(canSubmitTradeOffer(1, 2, [10], [20])).toBe(true);
    expect(canSubmitTradeOffer(1, 1, [10], [20])).toBe(false);
    expect(canSubmitTradeOffer(1, 2, [], [20])).toBe(false);
    expect(canSubmitTradeOffer(1, 2, [10], [])).toBe(false);
    expect(canSubmitTradeOffer(null, 2, [10], [20])).toBe(false);
  });

  it("builds the backend trade offer payload from selected players", () => {
    expect(
      buildTradeOfferPayload({
        ownedTeamId: 1,
        opponentTeamId: 2,
        giveIds: [10, 11],
        receiveIds: [20],
        message: "Swap depth for starter",
      })
    ).toEqual({
      proposing_team_id: 1,
      receiving_team_id: 2,
      proposing_items: [{ player_id: 10 }, { player_id: 11 }],
      receiving_items: [{ player_id: 20 }],
      message: "Swap depth for starter",
    });
  });

  it("normalizes trade statuses for the UI", () => {
    expect(tradeStatusLabel("proposed")).toBe("Pending");
    expect(tradeStatusLabel("commissioner_review")).toBe("Accepted · Commissioner Review");
    expect(tradeStatusLabel("processed")).toBe("processed");
  });

  it("rejects invalid payloads before hitting the API", () => {
    expect(() =>
      buildTradeOfferPayload({ ownedTeamId: 1, opponentTeamId: 2, giveIds: [], receiveIds: [20] })
    ).toThrow("Select at least one player");
  });
});
