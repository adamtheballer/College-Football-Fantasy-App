// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

const renderChart = (points: Array<{ week: number; value: number | null; actualValue?: number | null; source: "preseason" | "current" | "published" | "actual" | "bye" }>) =>
  render(
    <PlayerTrajectoryChart
      ariaLabel="Projection trajectory"
      points={points}
      yLabel="Points"
      yMax={30}
      valueFormatter={(value) => `${value.toFixed(1)} pts`}
      seriesKind="projection"
    />,
  );

describe("PlayerTrajectoryChart", () => {
  afterEach(cleanup);

  it("renders a canonical weekly preweek baseline without inventing a preseason point", () => {
    renderChart([{ week: 1, value: 18.4, source: "published" }]);

    expect(screen.getByText("Projected until weekly finalization • Standard CFFB scoring")).toBeTruthy();
    expect(screen.getByText("Preweek")).toBeTruthy();
    expect(screen.getByText("Weekly projection")).toBeTruthy();
    expect(screen.getByText("Final fantasy points")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    expect(screen.queryByTestId("trajectory-projection-line")).toBeNull();
    expect(screen.queryByTestId("trajectory-actual-line")).toBeNull();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
  });

  it("does not draw multiple future forecasts returned by an older server", () => {
    renderChart([{week: 1, value: 20.1, source: "published"}, {week: 2, value: 18.4, source: "published"}]);
    expect(screen.queryByTestId("trajectory-projection-line")).toBeNull();
    expect(screen.getByRole("img").querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
  });

  it("anchors the single dotted forecast to the last finalized actual without adding a point", () => {
    renderChart([{week: 6, value: 18.4, source: "actual"}, {week: 7, value: 21.2, source: "published"}]);
    expect(screen.getByTestId("trajectory-projection-line").getAttribute("stroke-dasharray")).toBe("7 7");
    expect(screen.getByRole("img").querySelectorAll("circle")).toHaveLength(2);
    expect(screen.queryByTestId("trajectory-actual-line")).toBeNull();
  });

  it("uses solid blue for all consecutive value history and supports negative actual points", () => {
    const {unmount} = render(<PlayerTrajectoryChart ariaLabel="Value" points={[{week:0,value:91,source:"preseason"},{week:1,value:80,source:"published"}]} yLabel="Value" yMax={100} valueFormatter={String} />);
    expect(screen.getByTestId("trajectory-value-line").getAttribute("stroke")).toBe("#2f80ff");
    expect(screen.getByTestId("trajectory-value-line").getAttribute("stroke-dasharray")).toBeNull();
    unmount();
    renderChart([{week:1,value:-2,source:"actual"},{week:2,value:0,source:"actual"}]);
    expect(screen.getByTestId("trajectory-point-week-1").getAttribute("cy")).not.toBe(screen.getByTestId("trajectory-point-week-2").getAttribute("cy"));
  });

  it("uses blue only for actual fantasy-point totals", () => {
    renderChart([{ week: 1, value: 22.6, source: "actual" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelector("title")?.textContent).toContain("actual fantasy points");
  });

  it("connects consecutive actual fantasy totals with a solid blue line", () => {
    renderChart([
      { week: 1, value: 17.1, source: "actual" },
      { week: 2, value: 24.2, source: "actual" },
    ]);

    const actualLine = screen.getByTestId("trajectory-actual-line");
    expect(actualLine.getAttribute("stroke")).toBe("#2f80ff");
    expect(actualLine.getAttribute("stroke-dasharray")).toBeNull();
    expect(screen.queryByTestId("trajectory-projection-line")).toBeNull();
  });

  it("replaces a completed week's pregame estimate with its one final total", () => {
    renderChart([{ week: 1, value: 18.4, actualValue: 25.2, source: "published" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#5ee7ff']")).toHaveLength(0);
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelector("title")?.textContent).toBe("Week 1 actual fantasy points (Finalized): 25.2 pts • Projected 18.4 pts");
  });

  it("keeps each final total under the week that produced it", () => {
    renderChart([
      { week: 1, value: 20.0, actualValue: 17.1, source: "published" },
      { week: 2, value: 19.0, actualValue: 4.2, source: "published" },
    ]);

    const weekOne = screen.getByTestId("trajectory-point-week-1");
    const weekTwo = screen.getByTestId("trajectory-point-week-2");
    expect(weekOne.getAttribute("cx")).not.toBe(weekTwo.getAttribute("cx"));
    expect(weekOne.getAttribute("aria-label")).toContain("Week 1 actual fantasy points (Finalized): 17.1 pts");
    expect(weekTwo.getAttribute("aria-label")).toContain("Week 2 actual fantasy points (Finalized): 4.2 pts");
  });

  it("shows a precise value on hover and lets touch users toggle that value", () => {
    renderChart([{ week: 1, value: 18.4, source: "published" }]);

    const point = screen.getByTestId("trajectory-point-week-1");
    fireEvent.pointerEnter(point);
    expect(screen.getByTestId("trajectory-point-value").textContent).toContain("18.4 pts");

    fireEvent.pointerLeave(point);
    expect(screen.queryByTestId("trajectory-point-value")).toBeNull();

    fireEvent.click(point);
    expect(screen.getByTestId("trajectory-point-value").textContent).toContain("18.4 pts");
    fireEvent.click(point);
    expect(screen.queryByTestId("trajectory-point-value")).toBeNull();
  });

  it("keeps the value-history legend separate from the weekly points semantics", () => {
    render(
      <PlayerTrajectoryChart
        ariaLabel="Value trajectory"
        points={[{ week: 0, value: 91, source: "preseason" }]}
        yLabel="Value"
        yMax={100}
        valueFormatter={(value) => value.toFixed(0)}
        seriesKind="value"
      />,
    );

    expect(screen.getByText("Preseason baseline — weekly snapshots begin at Week 1")).toBeTruthy();
    expect(screen.getByText("Published weekly snapshot")).toBeTruthy();
    expect(screen.queryByText("Actual fantasy points")).toBeNull();
  });

  it("renders a bye without fabricating a zero-valued projection", () => {
    renderChart([{ week: 2, value: null, source: "bye" }]);

    expect(screen.getByText("BYE")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(0);
  });
});


describe("Chart refresh identity", () => {
  afterEach(cleanup);
  it("retains the selected week when an earlier week arrives and a projection finalizes", () => {
    const props = {ariaLabel:"Refresh", yLabel:"Points", yMax:30, valueFormatter:String, seriesKind:"projection" as const};
    const {rerender} = render(<PlayerTrajectoryChart {...props} points={[{week:6,value:18.4,source:"actual"},{week:7,value:21.2,source:"published"}]} />);
    fireEvent.click(screen.getByTestId("trajectory-point-week-7"));
    rerender(<PlayerTrajectoryChart {...props} points={[{week:5,value:0,source:"actual"},{week:6,value:18.4,source:"actual"},{week:7,value:24.6,forecastValue:21.2,source:"actual"},{week:8,value:23,source:"published"}]} />);
    expect(screen.getByTestId("trajectory-point-week-7").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("trajectory-point-value").textContent).toContain("24.6 • Projected 21.2");
    expect(screen.getByTestId("trajectory-point-week-6").getAttribute("aria-label")).not.toContain("Projected");
  });
  it("does not manufacture original forecasts from actual-only records", () => {
    renderChart([{week:6,value:18.4,source:"actual"}]);
    expect(screen.getByTestId("trajectory-point-week-6").getAttribute("aria-label")).not.toContain("Projected");
  });
  it("breaks the solid path across a missing week", () => {
    renderChart([{week:4,value:10,source:"actual"},{week:5,value:11,source:"actual"},{week:7,value:12,source:"actual"}]);
    expect(screen.getByTestId("trajectory-actual-line").getAttribute("d")?.match(/M/g)).toHaveLength(2);
  });
});

describe("Unfinished historical gaps",()=>{
  afterEach(cleanup);
  it("labels a delayed week without claiming it is finalized or scoring it as zero",()=>{
    render(<PlayerTrajectoryChart ariaLabel="Pending week" points={[{week:2,value:null,source:"unavailable",isFinalized:false}]} yLabel="Points" yMax={30} valueFormatter={String} seriesKind="projection" />);
    const chart=screen.getByRole("img");
    expect(chart.querySelector("title")?.textContent).toContain("awaiting weekly finalization");
    expect(chart.querySelectorAll("circle")).toHaveLength(0);
  });
});


it("fits a late-week forecast inside a narrow phone canvas before any scrolling", () => {
  const measure = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 300, height: 312, x: 0, y: 0, top: 0, left: 0, right: 300, bottom: 312, toJSON: () => ({}) });
  try {
    renderChart([{ week: 7, value: 21.2, source: "published" }]);
    const svg = screen.getByRole("img");
    expect(svg.getAttribute("viewBox")).toBe("0 0 300 312");
    expect(svg.getAttribute("class")).not.toContain("min-w");
    const point = screen.getByTestId("trajectory-point-week-7");
    expect(Number(point.getAttribute("cx"))).toBeGreaterThan(54);
    expect(Number(point.getAttribute("cx"))).toBeLessThan(274);
    expect(screen.getByText("W13")).toBeTruthy();
  } finally { cleanup(); measure.mockRestore(); }
});
