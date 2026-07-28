// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiGet: state.apiGet }));

import { RuntimeDiagnosticsPanel } from "./RuntimeDiagnosticsPanel";

afterEach(() => {
  cleanup();
  state.apiGet.mockReset();
});

describe("RuntimeDiagnosticsPanel", () => {
  it("shows the API identity and migration revision returned by the runtime endpoint", async () => {
    state.apiGet.mockResolvedValueOnce({
      status: "ready",
      environment: "production",
      api_build_sha: "0123456789abcdef",
      database: "ready",
      migrations: "ready",
      expected_revisions: ["0067_split_projection_fg"],
      current_revisions: ["0067_split_projection_fg"],
      detail: "database and Alembic revision are ready",
    });

    render(<RuntimeDiagnosticsPanel />);

    await waitFor(() => expect(screen.getByText("0123456789ab")).toBeTruthy());
    expect(screen.getByText("0067_split_projection_fg")).toBeTruthy();
    expect(screen.getByText("production")).toBeTruthy();
    expect(state.apiGet).toHaveBeenCalledWith("/health/runtime");
  });

  it("keeps Settings usable and explains a runtime diagnostics request failure", async () => {
    state.apiGet.mockRejectedValueOnce(new Error("unavailable"));

    render(<RuntimeDiagnosticsPanel />);

    expect((await screen.findByRole("alert")).textContent).toContain("Runtime diagnostics are unavailable");
  });
});
