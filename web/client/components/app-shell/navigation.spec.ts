import { describe, expect, it } from "vitest";

import {
  getMobileNavItems,
  getShellNavItems,
  isAuthFlowRoute,
  isCreateLeagueRoute,
  isDraftRoomRoute,
  isSaturdayPick6Route,
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
    expect(isSaturdayPick6Route("/saturday-pick-6")).toBe(true);
    expect(isSaturdayPick6Route("/")).toBe(false);
    expect(isAuthFlowRoute("/login")).toBe(true);
    expect(isAuthFlowRoute("/beta-access")).toBe(true);
    expect(isAuthFlowRoute("/signup")).toBe(true);
    expect(isAuthFlowRoute("/league/1/roster")).toBe(false);
  });

  it("keeps guest navigation small and includes sign-in", () => {
    const items = getShellNavItems(null, false);

    expect(items.map((item) => item.name)).toEqual([
      "HOME",
      "LEAGUES",
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

  it("shows the report-bug entry only when the API supplies a support address", () => {
    expect(getShellNavItems(user, true)).not.toContainEqual(
      expect.objectContaining({ name: "REPORT BUG" }),
    );
    expect(getShellNavItems(user, true, 0, true)).toContainEqual(
      expect.objectContaining({ name: "REPORT BUG", path: "/report-bug" }),
    );
  });

  it("keeps Coming Soon linked to the roadmap only", () => {
    expect(getShellNavItems(user, true)).toContainEqual(
      expect.objectContaining({ name: "COMING SOON", path: "/coming-soon" }),
    );
  });

  it("keeps Saturday Pick 6 out of permanent authenticated desktop navigation", () => {
    expect(getShellNavItems(user, true)).not.toContainEqual(
      expect.objectContaining({ name: "SATURDAY PICK 6", path: "/saturday-pick-6" }),
    );
  });

  it("surfaces an unread badge for the chats sidebar item", () => {
    const chats = getShellNavItems(user, true, 12).find((item) => item.name === "CHATS");
    const cappedChats = getShellNavItems(user, true, 120).find((item) => item.name === "CHATS");

    expect(chats?.badge).toBe("12");
    expect(cappedChats?.badge).toBe("99+");
  });

  it("keeps mobile navigation focused on the primary destinations", () => {
    const mobileItems = getMobileNavItems(getShellNavItems(user, true, 1, true));
    const mobile = mobileItems.map((item) => item.name);

    expect(mobile).toEqual(["HOME", "LEAGUES", "CHATS", "MOCK DRAFT"]);
    expect(mobile).toHaveLength(4);
    expect(mobileItems.find((item) => item.name === "CHATS")?.badge).toBe("1");
    expect(mobile).not.toContain("REPORT BUG");
    expect(mobile).not.toContain("SIGN OUT");
    expect(mobile).not.toContain("SATURDAY PICK 6");
  });

  it("preserves stable onboarding target IDs", () => {
    expect(navDomId("INJURY CENTER")).toBe("nav-injury-center");
    expect(navDomId("SIGN OUT")).toBe("nav-sign-out");
  });
});
