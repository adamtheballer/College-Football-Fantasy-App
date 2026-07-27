import { describe, expect, it } from "vitest";

import { resolveTradeOfferReturnPath, tradeOfferPath } from "./trade-links";

describe("trade offer links", () => {
  it("carries a valid chat return route with the trade link", () => {
    expect(tradeOfferPath(4, 18, "/chats?leagueId=4&threadId=7"))
      .toBe("/leagues/4/trades/18?returnTo=%2Fchats%3FleagueId%3D4%26threadId%3D7");
  });

  it("only resolves same-app chat routes as a close destination", () => {
    expect(resolveTradeOfferReturnPath("/chats?leagueId=4&threadId=7"))
      .toBe("/chats?leagueId=4&threadId=7");
    expect(resolveTradeOfferReturnPath("https://example.com/chats")).toBe("/trade");
    expect(resolveTradeOfferReturnPath("/leagues/create")).toBe("/trade");
  });
});
