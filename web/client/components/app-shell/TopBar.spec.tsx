// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { TopBar } from "./TopBar";

describe("TopBar", () => {
  it("shows the compact College Fantasy Football brand without release-stage labels", () => {
    render(
      <MemoryRouter>
        <TopBar isLoggedIn user={null} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "College Fantasy Football" }).getAttribute("href")).toBe("/");
    expect(screen.getByRole("img", { name: "CFFB — College Fantasy Football" })).toBeTruthy();
    expect(screen.queryByText("Early Access")).toBeNull();
    expect(screen.queryByText("Beta")).toBeNull();
  });
});
