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

  it("routes injury and announcement taps to existing protected pages", () => {
    expect(resolveNotificationPath({ type: "player", league_id: 4, resource_id: 18 })).toBe("/injury-center?playerId=18&leagueId=4");
    expect(resolveNotificationPath({ type: "announcement", league_id: null, resource_id: 12 })).toBe("/announcements/12");
    expect(resolveNotificationPath({ type: "matchup", league_id: 4, resource_id: 8, week: 7 })).toBe("/league/4/matchup?week=7&matchup=8");
    expect(resolveNotificationPath({ type: "player", league_id: -1, resource_id: 18 })).toBe("/alerts");
  });

  it("keeps incomplete or missing destinations inside the notification center", () => {
    expect(resolveNotificationPath({ type: "trade", league_id: 4, resource_id: null }))
      .toBe("/trade");
    expect(resolveNotificationPath(null)).toBe("/alerts");
  });
});

// Challenges are app-wide and do not require a league membership.
it("routes server-authorized challenge notifications without a league",()=>{expect(resolveNotificationPath({type:"challenge",league_id:null,resource_id:12})).toBe("/weekly-challenges/12");});
