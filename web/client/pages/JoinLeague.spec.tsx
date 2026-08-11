// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  apiPost: vi.fn(),
  inviteCode: "",
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ inviteCode: state.inviteCode || undefined }),
  };
});

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ isLoggedIn: true }),
}));

vi.mock("@/lib/api", () => ({
  apiPost: state.apiPost,
}));

import JoinLeague from "./JoinLeague";

const preview = {
  id: 12,
  name: "Saturday League",
  commissioner_name: "Commissioner",
  max_teams: 12,
  member_count: 1,
  is_private: true,
  draft_datetime_utc: null,
  timezone: "America/New_York",
  scoring_preset: "standard",
};

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

const renderPage = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <JoinLeague />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("JoinLeague preview", () => {
  beforeEach(() => {
    state.apiPost.mockReset();
    state.inviteCode = "";
  });

  afterEach(cleanup);

  it("keeps the newest preview when an older request fails later", async () => {
    const firstRequest = deferred<typeof preview>();
    const secondRequest = deferred<typeof preview>();
    state.apiPost.mockImplementationOnce(() => firstRequest.promise).mockImplementationOnce(() => secondRequest.promise);
    state.inviteCode = "FIRSTINVITE";

    const view = renderPage();
    await waitFor(() => expect(state.apiPost).toHaveBeenCalledTimes(1));

    state.inviteCode = "SECONDINVITE";
    view.rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <JoinLeague />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(state.apiPost).toHaveBeenCalledTimes(2));

    secondRequest.resolve(preview);
    await waitFor(() => expect(screen.getByText("League Preview")).toBeTruthy());

    firstRequest.reject(new Error("Internal Server Error"));
    await Promise.resolve();

    expect(screen.getByText("League Preview")).toBeTruthy();
    expect(screen.queryByText("Internal Server Error")).toBeNull();
  });

  it("does not expose a raw server error for the current request", async () => {
    state.apiPost.mockRejectedValueOnce(new Error("Internal Server Error"));
    renderPage();

    fireEvent.change(screen.getByPlaceholderText("ENTER INVITE CODE"), { target: { value: "INVITECODE" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview League" }));

    await waitFor(() => {
      expect(screen.getByText("We could not load this invite just now. Please try again.")).toBeTruthy();
    });
    expect(screen.queryByText("Internal Server Error")).toBeNull();
  });
});
