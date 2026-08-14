import { describe, expect, it } from "vitest";

import { resolveNotificationPath } from "./notifications";

describe("notification destination routing", () => {
  it("only produces routes from the typed server destination", () => {
    expect(resolveNotificationPath({ type: "draft", league_id: 4, resource_id: null }))
      .toBe("/league/4/draft");
    expect(resolveNotificationPath({ type: "trade", league_id: 4, resource_id: 18 }))
      .toBe("/leagues/4/trades/18");
    expect(resolveNotificationPath({ type: "chat", league_id: 4, resource_id: 7 }))
      .toBe("/chats?leagueId=4&threadId=7");
  });

  it("keeps incomplete or missing destinations inside the notification center", () => {
    expect(resolveNotificationPath({ type: "trade", league_id: 4, resource_id: null }))
      .toBe("/trade");
    expect(resolveNotificationPath(null)).toBe("/alerts");
  });
});
