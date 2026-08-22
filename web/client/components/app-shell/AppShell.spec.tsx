// @vitest-environment jsdom

import * as React from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell, shouldShowHomeHeader } from "./AppShell";

afterEach(cleanup);

function renderShell({
  compactContent,
  fixedViewport,
}: {
  compactContent: boolean;
  fixedViewport: boolean;
}) {
  return render(
    <AppShell
      navItems={[]}
      pathname="/"
      user={null}
      isLoggedIn={false}
      hideChrome
      hideFloatingActions
      compactContent={compactContent}
      fixedViewport={fixedViewport}
      onSignOut={vi.fn()}
      mainScrollRef={React.createRef<HTMLElement>()}
    >
      <div>Shell content</div>
    </AppShell>,
  );
}

describe("AppShell scroll ownership", () => {
  it("uses a quiet app canvas without decorative background effects", () => {
    const { container } = renderShell({
      compactContent: false,
      fixedViewport: false,
    });

    const effects = container.querySelector("[data-bg-effects='true']");
    expect(effects).toBeNull();
    expect(container.firstElementChild?.className).toContain("bg-cfb-canvas");
  });

  it("keeps standard pages on the single app-page scroller", () => {
    const { container } = renderShell({
      compactContent: false,
      fixedViewport: false,
    });
    const scrollArea = container.querySelector("main[data-app-scroll='true']");

    expect(scrollArea?.getAttribute("data-scroll-owner")).toBe("page");
    expect(scrollArea?.className).toContain("overflow-y-auto");
    expect(scrollArea?.className).toContain("overflow-x-hidden");
    expect(scrollArea?.className).toContain("overscroll-x-none");
    expect(scrollArea?.className).toContain("touch-pan-y");
    expect(container.firstElementChild?.className).toContain("flex-col");
    expect(container.firstElementChild?.className).toContain("overflow-clip");
    expect(container.firstElementChild?.className).toContain("pt-[env(safe-area-inset-top)]");
    expect(scrollArea?.className).not.toMatch(/(^|\s)h-full(\s|$)/);
  });

  it("contains draft rooms without mutating the document scroll lock", () => {
    document.body.style.overflow = "auto";
    const { container } = renderShell({
      compactContent: true,
      fixedViewport: true,
    });
    const scrollArea = container.querySelector("main[data-app-scroll='true']");

    expect(scrollArea?.getAttribute("data-scroll-owner")).toBe("draft-room");
    expect(scrollArea?.className).toContain("overflow-hidden");
    expect(scrollArea?.className).toContain("overscroll-x-none");
    expect(scrollArea?.className).not.toContain("overflow-y-auto");
    expect(document.body.style.overflow).toBe("auto");
  });

  it("keeps compact non-draft routes on the normal page scroller", () => {
    const { container } = renderShell({
      compactContent: true,
      fixedViewport: false,
    });
    const scrollArea = container.querySelector("main[data-app-scroll='true']");

    expect(scrollArea?.getAttribute("data-scroll-owner")).toBe("page");
    expect(scrollArea?.className).toContain("overflow-y-auto");
  });

  it("removes the shell gutter for pages that provide their own safe spacing", () => {
    const { container } = renderShell({
      compactContent: true,
      fixedViewport: false,
    });

    const content = container.querySelector("main[data-app-scroll='true'] > div");
    expect(content?.className).toContain("p-0");
    expect(content?.className).not.toContain("px-4");
  });

  it("shows the Early Access header only on the home route", () => {
    expect(shouldShowHomeHeader("/", false)).toBe(true);
    expect(shouldShowHomeHeader("/leagues/roster", false)).toBe(false);
    expect(shouldShowHomeHeader("/chats", false)).toBe(false);
    expect(shouldShowHomeHeader("/drafts/123", false)).toBe(false);
    expect(shouldShowHomeHeader("/", true)).toBe(false);
  });
});
