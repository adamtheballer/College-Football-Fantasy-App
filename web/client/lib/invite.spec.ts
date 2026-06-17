import { describe, expect, it } from "vitest";

import { buildLeagueInviteLink, extractInviteCodeFromInput, normalizeInviteCode } from "./invite";

describe("league invite helpers", () => {
  it("normalizes invite codes", () => {
    expect(normalizeInviteCode(" abc-123 ")).toBe("ABC123");
  });

  it("extracts invite codes from direct codes and full links", () => {
    expect(extractInviteCodeFromInput("abcdefghijklmnopqrst")).toBe("ABCDEFGHIJKLMNOPQRST");
    expect(extractInviteCodeFromInput("https://app.example.com/join/abc123DEF456")).toBe("ABC123DEF456");
    expect(extractInviteCodeFromInput("https://app.example.com/leagues/join?code=abc123")).toBe("ABC123");
  });

  it("builds shareable league invite links from an origin", () => {
    expect(buildLeagueInviteLink("abc123", "https://app.example.com/")).toBe("https://app.example.com/join/ABC123");
  });
});
