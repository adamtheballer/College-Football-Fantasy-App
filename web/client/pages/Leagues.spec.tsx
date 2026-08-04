// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LeagueCard } from "./Leagues";

const props = {
  id: 1,
  name: "Saturday League",
  status: "pre_draft",
  teams: 12,
  memberCount: 1,
  draftLabel: "August 20",
  draftDateTime: "2026-08-20T19:00:00Z",
  isPrivate: true,
  draftStatus: "scheduled",
  onOpen: vi.fn(),
  onOpenDraft: vi.fn(),
};

afterEach(() => {
  cleanup();
  props.onOpen.mockReset();
  props.onOpenDraft.mockReset();
});

describe("LeagueCard", () => {
  it("renders the saved league image inside the trophy tile", () => {
    render(<LeagueCard {...props} iconUrl="https://images.example.com/saturday-league.png" />);

    expect(screen.getByRole("img", { name: "Saturday League league logo" }).getAttribute("src")).toBe(
      "https://images.example.com/saturday-league.png"
    );
    expect(screen.queryByLabelText("Default league trophy")).toBeNull();
  });

  it("keeps the trophy when the image is empty or fails to load", () => {
    const { rerender } = render(<LeagueCard {...props} iconUrl={null} />);
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();

    rerender(<LeagueCard {...props} iconUrl="https://images.example.com/missing.png" />);
    fireEvent.error(screen.getByRole("img", { name: "Saturday League league logo" }));
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();
  });
});
