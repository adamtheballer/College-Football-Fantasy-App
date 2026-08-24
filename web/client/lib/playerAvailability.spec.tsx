// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerAvailabilityIndicator, playerAvailabilityBadge, playerAvailabilityDotClass } from "./playerAvailability";

describe("player availability badges", () => {
  it("keeps active and unreported players free of a status marker", () => {
    expect(playerAvailabilityBadge("ACTIVE")).toBeNull();
    expect(playerAvailabilityBadge("UNREPORTED")).toBeNull();
    expect(playerAvailabilityBadge(null)).toBeNull();
  });

  it("maps every unavailable report to a red out marker", () => {
    expect(playerAvailabilityBadge("OUT_FOR_SEASON")).toMatchObject({ code: "O", label: "Out" });
    expect(playerAvailabilityBadge("inactive")).toMatchObject({ code: "O", label: "Out" });
    expect(playerAvailabilityBadge("IR")).toMatchObject({ code: "O", label: "Out" });
  });

  it("maps uncertain reports to a yellow questionable marker", () => {
    expect(playerAvailabilityBadge("DOUBTFUL")).toMatchObject({ code: "Q", label: "Questionable" });
    expect(playerAvailabilityBadge("day-to-day")).toMatchObject({ code: "Q", label: "Questionable" });
  });

  it("renders the marker beside the player name", () => {
    render(<PlayerAvailabilityIndicator status="OUT"><span>Ahmad Hardy</span></PlayerAvailabilityIndicator>);

    expect(screen.getByText("Ahmad Hardy")).toBeTruthy();
    expect(screen.getByLabelText("Out").textContent).toBe("O");
  });

  it("uses red for out, yellow for questionable, and green for verified active status dots", () => {
    expect(playerAvailabilityDotClass("OUT_FOR_SEASON")).toBe("bg-red-400");
    expect(playerAvailabilityDotClass("QUESTIONABLE")).toBe("bg-amber-300");
    expect(playerAvailabilityDotClass("ACTIVE")).toBe("bg-emerald-300");
  });
});
