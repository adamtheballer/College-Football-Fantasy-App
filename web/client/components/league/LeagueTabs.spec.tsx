// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { LeagueTabs } from "./LeagueTabs";

afterEach(cleanup);

describe("LeagueTabs", () => {
  it("uses one scroll-contained league rail on every league screen", () => {
    render(
      <MemoryRouter initialEntries={["/league/42/roster"]}>
        <LeagueTabs leagueId={42} />
      </MemoryRouter>,
    );

    const labels = screen.getAllByRole("link").map((link) => link.textContent);

    expect(labels).toEqual(["Roster", "Matchup", "Players", "Watchlist", "League"]);
    expect(screen.getByRole("link", { name: "Players" }).getAttribute("href")).toBe("/league/42/waivers");
    expect(screen.getByRole("link", { name: "Watchlist" }).getAttribute("href")).toBe("/league/42/watchlist");
    expect(screen.getByRole("link", { name: "League" }).getAttribute("href")).toBe("/league/42/settings");
    expect(screen.queryByRole("link", { name: "Waivers" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
    const rail = screen.getByRole("navigation", { name: "League sections" });
    expect(rail.className).toContain("overflow-x-auto");
    expect(rail.className).toContain("overscroll-x-contain");
    expect(rail.className).toContain("touch-pan-x");
  });
});
