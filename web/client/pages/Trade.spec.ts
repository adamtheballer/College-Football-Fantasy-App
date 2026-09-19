import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import type { RosterEntry } from "@/types/roster";
import { formatTradeError, getTradeOfferSentToast, toTradeRows } from "./Trade";

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
          image_url: "https://a.espncdn.com/i/headshots/college-football/players/full/7.png",
        },
      },
    ] as unknown as RosterEntry[]);

    expect(rows).toEqual([
      expect.objectContaining({
        playerId: 7,
        position: "RB",
        imageUrl: "https://a.espncdn.com/i/headshots/college-football/players/full/7.png",
      }),
    ]);
  });
});

describe("getTradeOfferSentToast", () => {
  it("uses a green success notification and identifies the receiving team", () => {
    expect(getTradeOfferSentToast("The Tigers")).toMatchObject({
      title: "Trade sent successfully",
      description: "Your offer is ready for The Tigers to review.",
      className: expect.stringContaining("bg-emerald-500"),
    });
  });
});
