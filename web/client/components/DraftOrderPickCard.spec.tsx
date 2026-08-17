// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DraftOrderPickCard } from "./DraftOrderPickCard";
import { getDraftedPlayerLastName, getDraftManagerInitials } from "@/lib/draftOrderCarousel";

describe("draft order pick card", () => {
  afterEach(cleanup);

  it("keeps suffixes and multi-word surnames in the compact completed-pick label", () => {
    expect(getDraftedPlayerLastName("Marvin Harrison Jr.")).toBe("Harrison Jr.");
    expect(getDraftedPlayerLastName("Amon-Ra St. Brown")).toBe("St. Brown");
    expect(getDraftedPlayerLastName("KJ Duff")).toBe("Duff");
  });

  it("uses manager initials for a real draft card and reveals the completed pick", () => {
    render(<DraftOrderPickCard managerName="Adam Bajdechi" isCpu={false} round={1} roundPick={2} playerName="Jeremiah Smith" />);

    expect(screen.getByText("Adam Bajdechi")).toBeTruthy();
    expect(screen.getByLabelText("Adam Bajdechi initials AB").textContent).toBe("AB");
    expect(screen.getByText("(1.2)")).toBeTruthy();
    expect(screen.getByTestId("draft-order-picked-player").textContent).toBe("Smith");
    expect(getDraftManagerInitials("Adam Bajdechi")).toBe("AB");
    expect(getDraftManagerInitials("Codex")).toBe("C");
  });

  it("uses the bot indicator for mock draft cards and leaves future picks blank", () => {
    render(<DraftOrderPickCard managerName="Bot Team 3" isCpu round={2} roundPick={3} />);

    expect(screen.getByLabelText("Computer manager")).toBeTruthy();
    expect(screen.getByText("(2.3)")).toBeTruthy();
    expect(screen.getByTestId("draft-order-picked-player").textContent?.trim()).toBe("");
  });
});
