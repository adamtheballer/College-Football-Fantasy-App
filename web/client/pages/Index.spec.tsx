// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import Index from "./Index";

const session = vi.hoisted(() => ({ loggedIn: true }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({
  isLoggedIn: session.loggedIn, isBootstrapping: false,
  user: session.loggedIn ? { id: 7, firstName: "Home Manager" } : null,
}) }));
vi.mock("@/hooks/use-active-league", () => ({ useActiveLeagueId: () => ({ activeLeagueId: null, setActiveLeagueId: vi.fn() }) }));
vi.mock("@/hooks/use-leagues", () => ({ useLeagues: () => ({ data: [], isLoading: false }), useLeagueWorkspace: () => ({ data: undefined }) }));
vi.mock("@/lib/api", () => ({ apiGet: vi.fn().mockResolvedValue({ data: [] }) }));
afterEach(cleanup);

describe("Home without outdated contest promotion", () => {
  it.each([true, false])("has no Pick 6 promotion or contest links (signed in: %s)", async (loggedIn) => {
    session.loggedIn = loggedIn;
    const { container } = render(<MemoryRouter><Index /></MemoryRouter>);
    expect(container.textContent).not.toMatch(/pick\s*6|make your pick/i);
    expect(container.querySelector('a[href="/saturday-pick-6"]')).toBeNull();
    if (loggedIn) {
      expect(screen.getByText("Good to see you, Home Manager.")).toBeTruthy();
      expect(screen.getByText("Roster Status")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Create League" })).toBeTruthy();
      await screen.findByText("No alerts available");
    } else {
      expect(screen.getByRole("link", { name: "Create a League" }).getAttribute("href")).toBe("/signup");
      expect(screen.getByText("Waivers")).toBeTruthy();
    }
  });
});
