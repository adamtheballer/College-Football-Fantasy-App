// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { PlayerCardHeader } from "./PlayerCardHeader";

afterEach(cleanup);

describe("PlayerCardHeader injury status", () => {
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
        cfb27Rating={88}
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

    expect(screen.getByText("OUT FOR SEASON")).toBeTruthy();
    expect(screen.queryByText("Active")).toBeNull();
  });
});
