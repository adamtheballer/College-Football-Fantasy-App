import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import type { RosterEntry } from "@/types/roster";
import { formatTradeError, toTradeRows } from "./Trade";

describe("formatTradeError", () => {
  it("shows a permission detail returned by a trade mutation", () => {
    expect(
      formatTradeError(
        new ApiError(403, "Only the receiving manager can accept this trade."),
        "Fallback",
      ),
    ).toBe("Only the receiving manager can accept this trade.");
  });

  it("shows a lifecycle-conflict detail returned by a trade mutation", () => {
    expect(
      formatTradeError(
        new ApiError(409, "This trade is already cancelled."),
        "Fallback",
      ),
    ).toBe("This trade is already cancelled.");
  });
});

describe("toTradeRows", () => {
  it("excludes an empty roster placeholder instead of dereferencing a missing player", () => {
    const rows = toTradeRows([
      {
        id: 41,
        team_id: 9,
        slot: "BENCH",
        player: null,
      },
      {
        id: 42,
        team_id: 9,
        slot: "RB",
        player: {
          id: 7,
          name: "Healthy Runner",
          position: "RB",
          school: "Example University",
        },
      },
    ] as unknown as RosterEntry[]);

    expect(rows).toEqual([
      expect.objectContaining({ playerId: 7, position: "RB" }),
    ]);
  });
});
