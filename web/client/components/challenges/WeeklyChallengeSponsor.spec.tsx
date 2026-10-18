// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ChallengeSponsor } from "@/hooks/use-weekly-challenges";
import { WeeklyChallengeSponsor } from "./WeeklyChallengeSponsor";
import { WeeklyChallengesHome } from "./WeeklyChallengesHome";
import WeeklyChallenges from "@/pages/WeeklyChallenges";
import WeeklyChallengeDetail from "@/pages/WeeklyChallengeDetail";

const state = vi.hoisted(() => ({ sponsor: null as ChallengeSponsor | null }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 1 } }) }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/hooks/use-weekly-challenges", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-weekly-challenges")>()),
  useCurrentChallenges: () => ({
    data: {
      id: 8,
      season: 2026,
      week: state.sponsor ? 8 : 9,
      state: "Upcoming",
      next_rollover_at: "2026-10-28T12:00:00Z",
      challenges: [],
      sponsor: state.sponsor,
    },
  }),
  useChallenge: () => ({
    data: {
      id: 1,
      state: "Upcoming",
      kind: "lock",
      name: "Lock of the Week",
      rules: "Choose one winner",
      lock_at: null,
      server_now: "2026-10-22T12:00:00Z",
      games: [],
      sponsor: state.sponsor,
    },
  }),
}));
const sponsor: ChallengeSponsor = {
  name: "Pigskin Dispatch",
  label: "Sponsored by Pigskin Dispatch",
  tagline: "Football history, stories & podcasts",
  logo_url: "/assets/sponsors/PigskinDispatchLogo.png",
  youtube_url:
    "https://www.youtube.com/channel/UCQatEELNJL5GWry7eMXh-Qg?utm_source=chatgpt.com",
  season: 2026,
  week: 8,
};
afterEach(() => {
  cleanup();
  state.sponsor = null;
});
describe("Week-based challenge sponsorship", () => {
  it("uses the original logo without stretching and links to the exact channel", () => {
    render(<WeeklyChallengeSponsor sponsor={sponsor} />);
    const logo = screen.getByRole("img", { name: "Pigskin Dispatch logo" });
    expect(logo.getAttribute("src")).toBe(sponsor.logo_url);
    expect(logo.className).toContain("object-contain");
    const link = screen.getByRole("link", { name: "Watch on YouTube" });
    expect(link.getAttribute("href")).toBe(sponsor.youtube_url);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });
  for (const [name, Component] of [
    ["Home", WeeklyChallengesHome],
    ["challenge list", WeeklyChallenges],
    ["individual challenge", WeeklyChallengeDetail],
  ] as const) {
    it(`renders the sponsor on ${name} and removes it when the server changes weeks`, () => {
      state.sponsor = sponsor;
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <MemoryRouter>{children}</MemoryRouter>
        </QueryClientProvider>
      );
      const view = render(<Component />, { wrapper });
      expect(
        screen.getAllByRole("complementary", { name: "Week 8 sponsor" }),
      ).toHaveLength(1);
      expect(screen.getByText("Sponsored by Pigskin Dispatch")).toBeTruthy();
      state.sponsor = null;
      view.rerender(<Component />);
      expect(screen.queryByText("Sponsored by Pigskin Dispatch")).toBeNull();
      expect(
        screen.queryByRole("link", { name: "Watch on YouTube" }),
      ).toBeNull();
    });
  }
});
