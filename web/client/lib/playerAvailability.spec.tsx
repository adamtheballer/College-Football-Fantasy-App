// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerAvailabilityIndicator, playerAvailabilityBadge, playerAvailabilityDotClass } from "./playerAvailability";

describe("player availability badges", () => {
  it("keeps active and unreported players free of an injury badge", () => {
    expect(playerAvailabilityBadge("ACTIVE")).toBeNull();
    expect(playerAvailabilityBadge("UNREPORTED")).toBeNull();
    expect(playerAvailabilityBadge(null)).toBeNull();
  });

  it("maps every unavailable report to a red out marker", () => {
    expect(playerAvailabilityBadge("OUT_FOR_SEASON")).toMatchObject({ code: "O", label: "Out" });
    expect(playerAvailabilityBadge("inactive")).toMatchObject({ code: "O", label: "Out" });
    expect(playerAvailabilityBadge("IR")).toMatchObject({ code: "O", label: "Out" });
  });

  it("maps doubtful to a red D and questionable or probable to yellow Q/P", () => {
    expect(playerAvailabilityBadge("DOUBTFUL")).toMatchObject({ code: "D", label: "Doubtful" });
    expect(playerAvailabilityBadge("QUESTIONABLE")).toMatchObject({ code: "Q", label: "Questionable" });
    expect(playerAvailabilityBadge("PROBABLE")).toMatchObject({ code: "P", label: "Probable" });
    expect(playerAvailabilityBadge("day-to-day")).toMatchObject({ code: "Q", label: "Questionable" });
  });

  it("renders the marker beside the player name", () => {
    render(<PlayerAvailabilityIndicator status="OUT"><span>Ahmad Hardy</span></PlayerAvailabilityIndicator>);

    expect(screen.getByText("Ahmad Hardy")).toBeTruthy();
    expect(screen.getByLabelText("Out").textContent).toBe("O");
  });

  it("uses red for out/doubtful, yellow for questionable/probable, and green for active dots", () => {
    expect(playerAvailabilityDotClass("OUT_FOR_SEASON")).toBe("bg-red-400");
    expect(playerAvailabilityDotClass("DOUBTFUL")).toBe("bg-red-400");
    expect(playerAvailabilityDotClass("QUESTIONABLE")).toBe("bg-amber-300");
    expect(playerAvailabilityDotClass("PROBABLE")).toBe("bg-amber-300");
    expect(playerAvailabilityDotClass("ACTIVE")).toBe("bg-emerald-300");
  });

  it("shows an active green dot but no marker for an unreported status", () => {
    const { rerender } = render(<PlayerAvailabilityIndicator status="ACTIVE">Player</PlayerAvailabilityIndicator>);
    expect(screen.getByLabelText("Active").className).toContain("bg-emerald-300");
    rerender(<PlayerAvailabilityIndicator status="UNREPORTED">Player</PlayerAvailabilityIndicator>);
    expect(screen.queryByLabelText("Active")).toBeNull();
  });
});
