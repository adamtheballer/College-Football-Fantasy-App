// @vitest-environment jsdom
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PositionLeadersHome } from "./PositionLeadersHome";
import { PlayerRankingPortrait } from "./PlayerRankingPortrait";
const mocks = vi.hoisted(() => ({ leaders: vi.fn(), refetch: vi.fn() }));
vi.mock("@/hooks/use-player-rankings", async () => {
  const real = await vi.importActual("@/hooks/use-player-rankings");
  return { ...real, usePositionLeaders: mocks.leaders };
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const result = {
  period: "week",
  week: 7,
  scoring_label: "Standard scoring",
  updated_at: "2026-10-19T00:00:00Z",
  pending_players: 2,
  data: [
    {
      position: "RB",
      player: {
        id: 1,
        name: "Real Zero",
        school: "Texas",
        fantasy_points: 0,
        image_url: null,
      },
    },
  ],
};
const renderHome = () =>
  render(
    <MemoryRouter>
      <PositionLeadersHome />
    </MemoryRouter>,
  );
describe("verified Home positional leaders", () => {
  it("defaults to latest completed week, keeps zero and links filters without making up empty positions", () => {
    mocks.leaders.mockReturnValue({
      data: result,
      isLoading: false,
      isError: false,
    });
    renderHome();
    expect(mocks.leaders).toHaveBeenCalledWith("week");
    expect(screen.getByText("0.0")).toBeTruthy();
    expect(screen.getAllByText("Verified results pending.")).toHaveLength(4);
    expect(
      screen
        .getByRole("link", { name: /View RB rankings/ })
        .getAttribute("href"),
    ).toBe("/player-rankings?period=week&week=7&position=RB");
    expect(
      screen.getByRole("link", { name: /My leagues/ }).getAttribute("href"),
    ).toContain("view=mine");
    fireEvent.change(screen.getByLabelText("Leader results period"), {
      target: { value: "season" },
    });
    expect(mocks.leaders).toHaveBeenLastCalledWith("season");
  });
  it("offers retry on API failure instead of showing an empty successful table", () => {
    mocks.leaders.mockReturnValue({ isError: true, refetch: mocks.refetch });
    renderHome();
    expect(screen.getByRole("alert").textContent).toContain("couldn’t load");
    fireEvent.click(screen.getByRole("button", { name: "Retry leaders" }));
    expect(mocks.refetch).toHaveBeenCalledTimes(1);
  });
  it("uses a stable portrait fallback for disabled or broken images", () => {
    const view = render(
      <PlayerRankingPortrait
        player={{
          name: "Known Player",
          image_url: "https://example.invalid/a.png",
        }}
      />,
    );
    fireEvent.error(screen.getByRole("img"));
    expect(
      screen.getByLabelText("Known Player portrait unavailable"),
    ).toBeTruthy();
    view.rerender(
      <PlayerRankingPortrait
        player={{ name: "Known Player", image_url: null }}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
  });
});
