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
  avatarUrl: null,
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

const renderGuestNavigation = () => {
  const allItems = getShellNavItems(null, false);
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <MobileNavigation
        items={getMobileNavItems(allItems)}
        allItems={allItems}
        pathname="/login"
        onSignOut={vi.fn()}
      />
    </MemoryRouter>,
  );
};

describe("MobileNavigation", () => {
  it("keeps four tap-friendly primary destinations visible and opens the full sidebar in More", () => {
    renderNavigation();

    const navigation = screen.getByRole("navigation", { name: "Primary mobile navigation" });
    expect(navigation).toBeTruthy();
    expect(navigation.className).toContain("relative");
    expect(navigation.className).toContain("shrink-0");
    expect(navigation.className).not.toContain("fixed");
    expect(screen.getByLabelText("HOME")).toBeTruthy();
    expect(screen.getByLabelText("LEAGUES")).toBeTruthy();
    expect(screen.getByLabelText("CHATS: 2 unread chat messages")).toBeTruthy();
    expect(screen.getByLabelText("MOCK DRAFT")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open all navigation" })).toBeTruthy();
    expect(screen.queryByText("INJURY CENTER")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open all navigation" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "All navigation" })).toBeTruthy();
    expect(screen.getByText("Injury Center")).toBeTruthy();
    expect(screen.getByText("Alerts")).toBeTruthy();
    expect(screen.getByText("Report Bug")).toBeTruthy();
    expect(screen.getByText("Settings")).toBeTruthy();
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

    for (const label of ["Home", "Leagues", "Chats", "Draft", "More"]) {
      expect(screen.getByText(label).className).toContain("whitespace-nowrap");
    }
  });

  it("evenly distributes the guest tabs and places Sign In first", () => {
    renderGuestNavigation();

    const navigation = screen.getByRole("navigation", { name: "Primary mobile navigation" });
    const grid = navigation.querySelector('[data-mobile-nav-grid="true"]');
    expect((grid as HTMLDivElement | null)?.style.gridTemplateColumns).toBe("repeat(4, minmax(0, 1fr))");
    expect(screen.getAllByRole("link").slice(0, 3).map((link) => link.getAttribute("aria-label"))).toEqual([
      "SIGN IN",
      "LEAGUES",
      "SETTINGS",
    ]);
  });
});
