// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getMobileNavItems, getShellNavItems } from "./navigation";
import { MobileNavigation } from "./MobileNavigation";
import type { User } from "@/hooks/use-auth";

afterEach(cleanup);

const user: User = {
  id: 1,
  firstName: "Adam",
  email: "adam@example.com",
  isAdmin: false,
};

const renderNavigation = (onSignOut = vi.fn()) => {
  const allItems = getShellNavItems(user, true, 2, true);
  return {
    onSignOut,
    ...render(
      <MemoryRouter initialEntries={["/chats"]}>
        <MobileNavigation
          items={getMobileNavItems(allItems)}
          allItems={allItems}
          pathname="/chats"
          onSignOut={onSignOut}
        />
      </MemoryRouter>,
    ),
  };
};

describe("MobileNavigation", () => {
  it("keeps four tap-friendly primary destinations visible and opens the full sidebar in More", () => {
    renderNavigation();

    expect(screen.getByRole("navigation", { name: "Primary mobile navigation" })).toBeTruthy();
    expect(screen.getByLabelText("HOME")).toBeTruthy();
    expect(screen.getByLabelText("LEAGUES")).toBeTruthy();
    expect(screen.getByLabelText("CHATS: 2 unread chat messages")).toBeTruthy();
    expect(screen.getByLabelText("MOCK DRAFT")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open all navigation" })).toBeTruthy();
    expect(screen.queryByText("INJURY CENTER")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open all navigation" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "All navigation" })).toBeTruthy();
    expect(screen.getByText("INJURY CENTER")).toBeTruthy();
    expect(screen.getByText("ALERTS")).toBeTruthy();
    expect(screen.getByText("REPORT BUG")).toBeTruthy();
    expect(screen.getByText("SETTINGS")).toBeTruthy();
    expect(screen.getByRole("button", { name: "SIGN OUT" })).toBeTruthy();
  });

  it("keeps sign-out reachable from the More drawer", () => {
    const onSignOut = vi.fn();
    renderNavigation(onSignOut);

    fireEvent.click(screen.getByRole("button", { name: "Open all navigation" }));
    fireEvent.click(screen.getByRole("button", { name: "SIGN OUT" }));

    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("keeps the five primary labels on one line at narrow mobile widths", () => {
    renderNavigation();

    for (const label of ["HOME", "LEAGUES", "CHATS", "DRAFT", "More"]) {
      expect(screen.getByText(label).className).toContain("whitespace-nowrap");
    }
  });
});
