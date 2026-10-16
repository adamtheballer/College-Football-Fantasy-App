// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EntryForm } from "./WeeklyChallengeDetail";
import { ApiError } from "@/lib/api";
import {
  type Challenge,
  useChallengeState,
} from "@/hooks/use-weekly-challenges";

const mocks = vi.hoisted(() => ({ write: vi.fn() }));
vi.mock("@/lib/api", () => ({
  apiChallengeWrite: mocks.write,
  apiGet: vi.fn(),
  ApiError: class extends Error {
    constructor(
      public status: number,
      message: string,
      public detail?: unknown,
    ) {
      super(message);
    }
  },
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: 11 }, isBootstrapping: false }),
}));
const challenge = (patch: Partial<Challenge> = {}): Challenge => ({
  id: 13,
  round_id: 2,
  kind: "lock",
  name: "Lock of the Week",
  state: "Open",
  settlement_status: "published",
  version: 2,
  rules_version: "weekly-v1",
  rules: "Choose one winner",
  lock_at: "2026-10-17T15:55:00Z",
  server_now: "2026-10-17T15:50:00Z",
  published_at: "2026-10-14T12:00:00Z",
  scoring_rules: null,
  scoring_version: null,
  entry: null,
  games: [
    {
      id: 1,
      home_team: "Alabama",
      away_team: "Georgia",
      start_date: "2026-10-17T16:00:00Z",
      status: "scheduled",
      home_points: null,
      away_points: null,
    },
  ],
  players: [],
  underdogs: [],
  featured_game_id: null,
  cancellation_reason: null,
  draft_config: null,
  ...patch,
});
function mount(c = challenge(), accountId = 11) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <EntryForm challenge={c} accountId={accountId} onSaved={vi.fn()} />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  mocks.write.mockReset();
  sessionStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("official weekly entry", () => {
  it("shows submission confirmation only after the server persists it", async () => {
    let resolve!: (value: unknown) => void;
    mocks.write.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Alabama" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Submit Official Entry" }),
    );
    expect(screen.queryByText("Your official entry is submitted.")).toBeNull();
    await waitFor(() =>
      expect(mocks.write).toHaveBeenCalledWith(
        11,
        "PUT",
        "/weekly-challenges/challenges/13/entry",
        expect.objectContaining({
          expected_revision: 0,
          submit: true,
          selections: [{ game_id: 1, team: "Alabama" }],
        }),
      ),
    );
    await act(async () => resolve({ revision: 1, status: "submitted" }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain(
        "official entry is submitted",
      ),
    );
  });
  it("preserves a failed save and explains server deadline rejection", async () => {
    mocks.write.mockRejectedValue(
      new ApiError(409, "Closed", {
        code: "DEADLINE_PASSED",
        message: "Closed. The deadline has passed.",
      }),
    );
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Alabama" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Submit Official Entry" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "deadline has passed",
      ),
    );
    expect(
      screen
        .getByRole("button", { name: "✓ Alabama" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(screen.queryByText("Your official entry is submitted.")).toBeNull();
    expect(sessionStorage.getItem("cffb_challenge_draft_11_2_13_2")).toContain(
      "Alabama",
    );
  });
  it("does not restore another account's unsaved selections", () => {
    sessionStorage.setItem(
      "cffb_challenge_draft_11_2_13_2",
      JSON.stringify({
        picks: [{ game_id: 1, team: "Alabama" }],
        revision: 0,
        tiebreaker: "",
      }),
    );
    mount(challenge(), 22);
    expect(
      screen
        .getByRole("button", { name: "Alabama" })
        .getAttribute("aria-pressed"),
    ).toBe("false");
  });
  it("does not submit from a closed stale screen", () => {
    mount(challenge({ state: "Closed — Live" }));
    const button = screen.getByRole("button", {
      name: "Submit Official Entry",
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(mocks.write).not.toHaveBeenCalled();
  });
  it("saves a draft revision and uses that revision for official submission", async () => {
    mocks.write
      .mockResolvedValueOnce({ revision: 1, status: "draft" })
      .mockResolvedValueOnce({ revision: 2, status: "submitted" });
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Alabama" }));
    fireEvent.click(screen.getByRole("button", { name: "Save Draft" }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("Draft saved"),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Submit Official Entry" }),
    );
    await waitFor(() =>
      expect(mocks.write).toHaveBeenLastCalledWith(
        11,
        "PUT",
        expect.any(String),
        expect.objectContaining({ expected_revision: 1, submit: true }),
      ),
    );
  });
  it("limits Fantasy Five slots to the published position pool and distinct selections", () => {
    mount(
      challenge({
        kind: "fantasy5",
        name: "Fantasy Five",
        players: [
          {
            id: 1,
            game_id: 1,
            name: "QB One",
            school: "Alabama",
            position: "QB",
            image_url: null,
          },
          {
            id: 2,
            game_id: 1,
            name: "RB One",
            school: "Alabama",
            position: "RB",
            image_url: null,
          },
        ],
      }),
    );
    const flex = screen.getByRole("combobox", {
      name: "FLEX player",
    }) as HTMLSelectElement;
    expect(flex.textContent).not.toContain("QB One");
    fireEvent.change(screen.getByRole("combobox", { name: "RB player" }), {
      target: { value: "2" },
    });
    expect(
      Array.from(flex.options).find((x) => x.value === "2")!.disabled,
    ).toBe(true);
  });
});

it("closes presentation using server time even when the device wall clock is changed", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2040-01-01T00:00:00Z"));
  function State() {
    const state = useChallengeState({
      state: "Open",
      server_now: "2026-10-17T15:54:59Z",
      lock_at: "2026-10-17T15:55:00Z",
    });
    return <p>{state}</p>;
  }
  render(<State />);
  expect(screen.getByText("Open")).toBeTruthy();
  await act(async () => vi.advanceTimersByTime(1000));
  expect(screen.getByText("Closed — Live")).toBeTruthy();
});
