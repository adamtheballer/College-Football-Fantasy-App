// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

const renderChart = (points: Array<{ week: number; value: number; source: "preseason" | "current" | "published" }>) =>
  render(
    <PlayerTrajectoryChart
      ariaLabel="Projection trajectory"
      points={points}
      yLabel="Points"
      yMax={30}
      valueFormatter={(value) => `${value.toFixed(1)} pts`}
    />,
  );

describe("PlayerTrajectoryChart", () => {
  afterEach(cleanup);

  it("shows only a Week 0 dot before the season begins", () => {
    renderChart([{ week: 0, value: 18.4, source: "preseason" }]);

    expect(screen.getByText("Preseason baseline — weekly snapshots begin at Week 1")).toBeTruthy();
    expect(screen.getByText("W0")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(0);
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(1);
  });

  it("connects consecutive points only after a weekly snapshot exists", () => {
    renderChart([
      { week: 0, value: 18.4, source: "preseason" },
      { week: 1, value: 20.1, source: "published" },
    ]);

    expect(screen.getByText("Week 0–13 trajectory")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(1);
  });

  it("labels the Week 0 number as the current projection when it matches the player card", () => {
    renderChart([{ week: 0, value: 22.0, source: "current" }]);

    expect(screen.getByText("Current projection — weekly snapshots begin at Week 1")).toBeTruthy();
    expect(screen.getByText("Peak: 22.0 pts")).toBeTruthy();
  });
});
