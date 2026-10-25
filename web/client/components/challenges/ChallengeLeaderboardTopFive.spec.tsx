// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import fixture from "../../../shared/challenge-experiences.fixture.json";
import { apiGet } from "@/lib/api";
import type { Challenge } from "@/hooks/use-weekly-challenges";
import WeeklyChallengeLeaderboard from "@/pages/WeeklyChallengeLeaderboard";
import { ChallengeResults } from "@/pages/WeeklyChallengeDetail";
import { ExperienceLeaderboard } from "./ExperienceLeaderboard";

vi.mock("@/lib/api", () => ({ apiGet: vi.fn(), apiChallengeWrite: vi.fn(), ApiError: class extends Error {} }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 99 } }) }));
vi.mock("@/hooks/use-leagues", () => ({ useLeagues: () => ({ data: [] }) }));
vi.mock("@/hooks/use-weekly-challenges", async (original) => ({
  ...await original<typeof import("@/hooks/use-weekly-challenges")>(),
  useCurrentChallenges: () => ({ data: { id: 8, season: 2026, week: 8, challenges: [] } }),
}));

const rows = Array.from({ length: 10 }, (_, i) => ({
  user_id: i + 1, display_name: `Leader ${i + 1}`, username: null,
  avatar_url: null, profile_url: `/managers/${i + 1}`,
  points: 100 - i, rank: i + 1, status: "final", selections: null,
}));
const mine = { ...rows[9], user_id: 99, display_name: "Outside cutoff", rank: 30 };
const challenge = fixture.challenges[1] as unknown as Challenge;
function mount(element: React.ReactNode) {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })}>{element}</QueryClientProvider></MemoryRouter>);
}
beforeEach(() => { vi.mocked(apiGet).mockReset(); });
afterEach(cleanup);

it("shows only five overall point leaders in weekly and season views despite a legacy response", async () => {
  vi.mocked(apiGet).mockImplementation(async <T,>(path: string) =>
    (path.endsWith("/history") ? [] : { season: 2026, week: 8, data: rows, your_rank: mine }) as T);
  mount(<WeeklyChallengeLeaderboard />);
  await screen.findByText("Leader 5");
  expect(screen.getAllByRole("link", { name: /Leader \d/ })).toHaveLength(5);
  expect(screen.queryByText("Leader 6")).toBeNull();
  expect(screen.queryByText("Outside cutoff")).toBeNull();
  expect(screen.queryByText("Your Rank")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /^Season$/ }));
  await screen.findByRole("heading", { name: "Season Championship" });
  await screen.findByText("Leader 5");
  expect(screen.getAllByRole("link", { name: /Leader \d/ })).toHaveLength(5);
});

it("bounds experience point standings and suppresses the extra personal row", async () => {
  vi.mocked(apiGet).mockResolvedValue({ data: rows, your_rank: mine, total: 30, unit: "fantasy points" });
  mount(<ExperienceLeaderboard challenge={challenge} />);
  await screen.findByText(/#5 Leader 5/);
  expect(screen.getAllByRole("link", { name: /Leader \d/ })).toHaveLength(5);
  expect(screen.queryByText(/Leader 6|Your rank|Outside cutoff/)).toBeNull();
});

it("requests the first five results with no pagination or personal-result exception", async () => {
  vi.mocked(apiGet).mockResolvedValue({
    data: rows.map((participant, i) => ({ participant, entry_id: i + 1, rank: i + 1,
      challenge_points: 10 - i, raw_points: 100 - i, status: "final", tiebreaker_error: null })),
    my_result: { participant: mine }, total: 30,
  });
  mount(<ChallengeResults challenge={{ ...challenge, kind: "lock", state: "Final" }} />);
  await screen.findByText(/Leader 5/);
  expect(apiGet).toHaveBeenCalledWith(expect.stringContaining("/results"), { limit: 5, offset: 0 });
  expect(screen.getAllByRole("link", { name: /Leader \d/ })).toHaveLength(5);
  expect(screen.queryByText(/Leader 6|Your Result|Outside cutoff/)).toBeNull();
  expect(screen.queryByRole("button", { name: /Next|Previous/ })).toBeNull();
});

it("shows at most five schools in Fan Wars", async () => {
  vi.mocked(apiGet).mockResolvedValue({ data: [], total: 0, school_standings: rows.map((row) => ({
    school_id: row.user_id, school: `School ${row.user_id}`, rank: row.rank,
    accuracy: 50, fan_points: row.points, active_fans: 5, correct_picks: 5, eligible_picks: 10,
  })) });
  mount(<ExperienceLeaderboard challenge={fixture.challenges[0] as unknown as Challenge} />);
  await screen.findByText("School 5");
  expect(screen.getAllByRole("row")).toHaveLength(6);
  expect(screen.queryByText("School 6")).toBeNull();
  expect(screen.queryByRole("button", { name: "Fan Accuracy" })).toBeNull();
  expect(apiGet).toHaveBeenCalledWith(expect.stringContaining("/leaderboard"), {
    metric: "power", conference: undefined, season: false,
  });
});
