// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import DraftHome from "./DraftHome";

vi.mock("@/hooks/use-leagues", () => ({
  useLeagues: () => ({ data: [] }),
}));

afterEach(cleanup);

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

it("allows mixed mock conferences and prevents deselecting the last choice", async () => {
  const user = userEvent.setup();
  const { unmount } = render(<MemoryRouter><DraftHome /></MemoryRouter>);
  for (const name of ["Big Ten", "Big 12", "ACC", "Independent"]) await user.click(screen.getByRole("button", { name }));
  const sec = screen.getByRole("button", {name: "SEC"});
  expect(sec.hasAttribute("disabled")).toBe(true);
  expect(sec.getAttribute("aria-pressed")).toBe("true");
  const start = screen.getByRole("link", { name: /start single-player mock/i });
  expect(start.getAttribute("href")).toContain("conferences=SEC");
  await user.click(screen.getByRole("button", {name: "ACC"}));
  expect(sec.hasAttribute("disabled")).toBe(false);
  expect(start.getAttribute("href")).toContain("conferences=SEC,ACC");
  unmount();
});
