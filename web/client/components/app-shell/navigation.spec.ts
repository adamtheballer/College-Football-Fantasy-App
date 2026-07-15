import { describe, expect, it } from "vitest";

import {
  getMobileNavItems,
  getShellNavItems,
  isAuthFlowRoute,
  isCreateLeagueRoute,
  isDraftRoomRoute,
  navDomId,
} from "./navigation";
import type { User } from "@/hooks/use-auth";

const user: User = {
  id: 1,
  firstName: "Adam",
  email: "adam@example.com",
  isAdmin: false,
};

describe("app shell navigation helpers", () => {
  it("detects routes that need draft-room chrome removed", () => {
    expect(isDraftRoomRoute("/draft/mock/single-player")).toBe(true);
    expect(isDraftRoomRoute("/league/abc-123/draft")).toBe(true);
    expect(isDraftRoomRoute("/league/abc-123/lobby")).toBe(false);
  });

  it("detects create-league and auth flow shell exceptions", () => {
    expect(isCreateLeagueRoute("/leagues/create")).toBe(true);
    expect(isCreateLeagueRoute("/leagues/join")).toBe(false);
    expect(isAuthFlowRoute("/login")).toBe(true);
    expect(isAuthFlowRoute("/verify-email")).toBe(false);
    expect(isAuthFlowRoute("/league/1/roster")).toBe(false);
  });

  it("keeps guest navigation small and includes sign-in", () => {
    const items = getShellNavItems(null, false);

    expect(items.map((item) => item.name)).toEqual([
      "HOME",
      "LEAGUES",
      "PLAYER COMPARE",
      "SETTINGS",
      "SIGN IN",
    ]);
  });

  it("includes admin scoring only for admin users", () => {
    expect(getShellNavItems(user, true).some((item) => item.name === "ADMIN SCORING")).toBe(false);
    expect(
      getShellNavItems({ ...user, isAdmin: true }, true).some(
        (item) => item.name === "ADMIN SCORING",
      ),
    ).toBe(true);
  });

  it("keeps mobile navigation focused on the primary destinations", () => {
    const items = getShellNavItems(user, true);
    const mobile = getMobileNavItems(items).map((item) => item.name);

    expect(mobile).toEqual(["HOME", "LEAGUES", "PLAYER COMPARE", "MOCK DRAFT", "SETTINGS"]);
    expect(mobile).not.toContain("SIGN OUT");
  });

  it("preserves stable onboarding target IDs", () => {
    expect(navDomId("INJURY CENTER")).toBe("nav-injury-center");
    expect(navDomId("SIGN OUT")).toBe("nav-sign-out");
  });
});
