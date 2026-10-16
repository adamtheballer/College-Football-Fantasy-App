// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { LeagueTabs } from "./LeagueTabs";

afterEach(cleanup);

describe("LeagueTabs", () => {
  it.each(["/league/42", "/league/42/roster/"])("marks the roster active for %s", (path) => {
    render(<MemoryRouter initialEntries={[path]}><LeagueTabs leagueId={42} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Roster" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getAllByRole("link").filter((link) => link.hasAttribute("aria-current"))).toHaveLength(1);
  });

  it("preserves the draft-only restriction before the league draft completes", () => {
    render(<MemoryRouter initialEntries={["/league/42/draft"]}><LeagueTabs leagueId={42} draftStatus="live" /></MemoryRouter>);
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Draft" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Draft" }).getAttribute("href")).toBe("/league/42/lobby");
  });

  it("uses one scroll-contained league rail on every league screen", () => {
    render(
      <MemoryRouter initialEntries={["/league/42/roster"]}>
        <LeagueTabs leagueId={42} />
      </MemoryRouter>,
    );

    const labels = screen.getAllByRole("link").map((link) => link.textContent);

    expect(labels).toEqual(["Roster", "Matchup", "Waiver Wire", "Watchlist", "Chat", "Settings"]);
    expect(screen.getByRole("link", { name: "Waiver Wire" }).getAttribute("href")).toBe("/league/42/waivers");
    expect(screen.getByRole("link", { name: "Watchlist" }).getAttribute("href")).toBe("/league/42/watchlist");
    expect(screen.getByRole("link", { name: "Chat" }).getAttribute("href")).toBe("/league/42/chat");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("href")).toBe("/league/42/settings");
    expect(screen.queryByRole("link", { name: "Playoffs" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Players" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Waivers" })).toBeNull();
    const rail = screen.getByRole("navigation", { name: "League sections" });
    expect(rail.className).toContain("overflow-x-auto");
    expect(rail.className).toContain("overscroll-x-contain");
    expect(rail.className).toContain("touch-pan-x");
    const tabRail = rail.firstElementChild as HTMLElement;
    expect(tabRail.className).toContain("md:grid");
    expect(tabRail.className).toContain("md:w-full");
    expect(tabRail.style.gridTemplateColumns).toBe("repeat(6, minmax(0, 1fr))");
  });

  it("keeps Chat active inside the league route instead of sending managers to the global chat page", () => {
    render(
      <MemoryRouter initialEntries={["/league/42/chat"]}>
        <LeagueTabs leagueId={42} />
      </MemoryRouter>,
    );

    const chat = screen.getByRole("link", { name: "Chat" });
    expect(chat.getAttribute("href")).toBe("/league/42/chat");
    expect(chat.className).toContain("text-cfb-text-primary");
  });
});
