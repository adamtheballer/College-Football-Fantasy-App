// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import PublicHome from "./PublicHome";

describe("PublicHome", () => {
  it("provides clear beta and sign-in routes without authenticated navigation", () => {
    render(<MemoryRouter><PublicHome /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "College Football Fantasy Is Finally Here" })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /join (the )?beta/i })[0].getAttribute("href")).toBe("/login?flow=beta");
    expect(screen.getAllByRole("link", { name: "Sign In" })[0].getAttribute("href")).toBe("/login");
    expect(screen.queryByText("Leagues")).toBeNull();
    expect(screen.queryByText("Settings")).toBeNull();
  });
});
