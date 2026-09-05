// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { formatPlayerCardPositionRank, PlayerCardHeader, resolvePlayerCardStatus } from "./PlayerCardHeader";

afterEach(cleanup);

describe("PlayerCardHeader injury status", () => {
  it("treats a missing official injury report as ACTIVE", () => {
    expect(resolvePlayerCardStatus({
      current_injury_status: null,
      about: { status: "Active", source: "espn" },
    } as never, "UNREPORTED")).toBe("ACTIVE");
  });

  it("normalizes provider casing for active labels", () => {
    expect(resolvePlayerCardStatus(undefined, "active")).toBe("ACTIVE");
  });

  it("renders the reviewed injury designation instead of generic Active availability", () => {
    render(
      <PlayerCardHeader
        card={{
          current_injury_status: "OUT_FOR_SEASON",
          about: { status: "Active", source: "local" },
          player: { id: 1, name: "Injured Player", position: "RB", school: "Georgia" },
          injuries: [],
          season_stats: [],
          historical_stats: null,
        } as never}
        currentValue={88}
        onClose={vi.fn()}
        palette={{
          headerBase: "bg-slate-900",
          markerA: "rgba(255,255,255,0.1)",
          markerB: "rgba(255,255,255,0.1)",
          markerC: "rgba(255,255,255,0.1)",
          pill: "bg-slate-800",
          silhouette: "from-slate-700 to-slate-800",
        }}
        player={{ id: 1, name: "Injured Player", position: "RB", school: "Georgia", status: "Active" }}
        position="RB"
        title="Player Card"
      />,
    );

    expect(screen.getAllByText("OUT FOR SEASON")).toHaveLength(2);
    expect(screen.queryByText("Active")).toBeNull();
    expect(screen.getByText("Current Value Rating")).toBeTruthy();
    expect(screen.getByTestId("player-card-status-dot").className).toContain("bg-red-400");
  });

  it("replaces value with a finalized cumulative positional rank", () => {
    render(
      <PlayerCardHeader
        card={{
          current_injury_status: null,
          about: { status: "Active", source: "local" },
          player: { id: 1, name: "Top Receiver", position: "WR", school: "Miami" },
          injuries: [],
          season_stats: [],
          season_positional_rank: { position: "WR", rank: 1, fantasy_points: 42.6, through_week: 1 },
          historical_stats: null,
        } as never}
        currentValue={96}
        onClose={vi.fn()}
        palette={{
          headerBase: "bg-slate-900",
          markerA: "rgba(255,255,255,0.1)",
          markerB: "rgba(255,255,255,0.1)",
          markerC: "rgba(255,255,255,0.1)",
          pill: "bg-slate-800",
          silhouette: "from-slate-700 to-slate-800",
        }}
        player={{ id: 1, name: "Top Receiver", position: "WR", school: "Miami", status: "Active" }}
        position="WR"
        title="Player Card"
      />,
    );

    expect(screen.getAllByText("Rank")).toHaveLength(2);
    expect(screen.getAllByText("WR 1")).toHaveLength(1);
    expect(screen.getByText("Rank WR 1")).toBeTruthy();
    expect(screen.queryByText("Current Value Rating")).toBeNull();
    expect(formatPlayerCardPositionRank({ position: "WR", rank: 1, fantasy_points: 42.6, through_week: 1 })).toBe("WR 1");
  });
});
