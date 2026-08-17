// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { LeagueTabs } from "./LeagueTabs";

afterEach(cleanup);

describe("LeagueTabs", () => {
  it("uses short mobile labels so five league sections fit without overlap", () => {
    render(
      <MemoryRouter initialEntries={["/league/42/roster"]}>
        <LeagueTabs leagueId={42} />
      </MemoryRouter>,
    );

    const mobileLabels = screen
      .getAllByRole("link")
      .map((link) => link.querySelector("span")?.textContent);

    expect(mobileLabels).toEqual(["Roster", "Matchup", "Waivers", "Watch", "Settings"]);
  });
});
