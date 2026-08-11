// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";

describe("DesktopSidebar", () => {
  it("uses the same Early Access beta identity as the compact header", () => {
    render(
      <MemoryRouter>
        <DesktopSidebar items={[]} pathname="/" onSignOut={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Early Access CFB Fantasy Beta" }).getAttribute("href")).toBe("/");
    expect(screen.getByText("Early Access")).toBeTruthy();
    expect(screen.getByText("Beta")).toBeTruthy();
    expect(screen.queryByText("College Football")).toBeNull();
  });
});
