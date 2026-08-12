// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { TopBar } from "./TopBar";

describe("TopBar", () => {
  it("labels the compact app brand as the Early Access beta", () => {
    render(
      <MemoryRouter>
        <TopBar isLoggedIn user={null} />
      </MemoryRouter>,
    );

    expect(
      screen
        .getByRole("link", { name: "Early Access CFB Fantasy Beta" })
        .getAttribute("href"),
    ).toBe("/");
    expect(screen.getByText("Early Access")).toBeTruthy();
    expect(screen.getByText("Beta")).toBeTruthy();
  });
});
