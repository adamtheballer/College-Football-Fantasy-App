// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import DraftHome from "./DraftHome";

vi.mock("@/hooks/use-leagues", () => ({
  useLeagues: () => ({ data: [] }),
}));

describe("DraftHome", () => {
  it("keeps the mock setup controls quiet while preserving their behavior", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <DraftHome />
      </MemoryRouter>
    );

    const startMock = screen.getByRole("link", { name: /start single-player mock/i });
    expect(startMock.className).toContain("shadow-none");
    expect(startMock.className).not.toContain("shadow-sm");

    await user.click(screen.getByRole("button", { name: "8 Teams" }));
    await user.click(screen.getByRole("button", { name: "90s" }));

    expect(startMock.getAttribute("href")).toContain("teams=8");
    expect(startMock.getAttribute("href")).toContain("timer=90");
  });
});
