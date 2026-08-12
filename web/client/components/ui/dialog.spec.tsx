// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./dialog";

afterEach(cleanup);

describe("DialogContent mobile containment", () => {
  it("keeps a long dialog inside the viewport with a reachable close control", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Review trade offer</DialogTitle>
          <DialogDescription>
            Long offers must remain readable on a phone.
          </DialogDescription>
          <div className="h-[120dvh]">Long trade details</div>
        </DialogContent>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog.className).toContain("max-h-[calc(100dvh-1.5rem)]");
    expect(dialog.className).toContain("overflow-y-auto");
    expect(dialog.className).toContain("overscroll-contain");
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  });
});
