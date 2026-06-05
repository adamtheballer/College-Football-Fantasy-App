import { describe, expect, it } from "vitest";

import MockDraftRoom from "./MockDraftRoom";
import SinglePlayerMockDraftRoom from "./SinglePlayerMockDraftRoom";
import MockDraftBoard from "./MockDraftBoard";

describe("mock draft room shared component routing", () => {
  it("uses the same room container for single-player and multiplayer aliases", () => {
    expect(SinglePlayerMockDraftRoom).toBe(MockDraftRoom);
    expect(MockDraftBoard).toBe(MockDraftRoom);
  });
});
