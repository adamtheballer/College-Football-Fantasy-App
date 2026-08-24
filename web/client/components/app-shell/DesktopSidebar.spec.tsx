// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";

describe("DesktopSidebar", () => {
  it("uses the same CFFB identity as the compact header", () => {
    render(
      <MemoryRouter>
        <DesktopSidebar items={[]} pathname="/" onSignOut={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "College Fantasy Football" }).getAttribute("href")).toBe("/");
    expect(screen.getByText("CFFB")).toBeTruthy();
    expect(screen.queryByText("Early Access")).toBeNull();
    expect(screen.queryByText("Beta")).toBeNull();
  });
});
