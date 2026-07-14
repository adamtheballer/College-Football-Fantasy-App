import { describe, expect, it } from "vitest";

import {
  getPositionBadgeClass,
  positionBadgeClasses,
  statCardToneClasses,
  statusBadgeClasses,
  statusBadgeLabels,
  surfaceCardVariants,
} from "./designSystem";

describe("fantasy design system variants", () => {
  it("uses semantic surface tokens for the default card foundation", () => {
    const classes = surfaceCardVariants();

    expect(classes).toContain("bg-cfb-surface");
    expect(classes).toContain("border-cfb-border-subtle");
  });

  it("provides distinct state badges for fantasy scoring states", () => {
    expect(statusBadgeClasses.live).toContain("score-live");
    expect(statusBadgeClasses.projected).toContain("score-projected");
    expect(statusBadgeClasses.final).toContain("score-final");
    expect(statusBadgeClasses.corrected).toContain("score-corrected");
    expect(statusBadgeClasses.delayed).toContain("score-delayed");
    expect(statusBadgeClasses.unavailable).toContain("score-unavailable");
    expect(statusBadgeClasses.locked).toContain("score-locked");
  });

  it("keeps state labels explicit for screen-reader and text fallback usage", () => {
    expect(statusBadgeLabels.live).toBe("Live");
    expect(statusBadgeLabels.projected).toBe("Projected");
    expect(statusBadgeLabels.unavailable).toBe("Unavailable");
  });

  it("maps known fantasy positions to readable badge classes", () => {
    expect(getPositionBadgeClass("QB")).toBe(positionBadgeClasses.QB);
    expect(getPositionBadgeClass("rb")).toBe(positionBadgeClasses.RB);
    expect(getPositionBadgeClass(" Flex ")).toBe(positionBadgeClasses.FLEX);
  });

  it("falls back safely for unknown or empty positions", () => {
    expect(getPositionBadgeClass("P")).toBe(positionBadgeClasses.DEFAULT);
    expect(getPositionBadgeClass(null)).toBe(positionBadgeClasses.DEFAULT);
    expect(getPositionBadgeClass(undefined)).toBe(positionBadgeClasses.DEFAULT);
  });

  it("defines a restrained shared palette for stat card tones", () => {
    expect(Object.keys(statCardToneClasses)).toEqual([
      "neutral",
      "brand",
      "pink",
      "gold",
      "success",
      "danger",
    ]);
    expect(statCardToneClasses.brand.frame).toContain("cfb-brand");
  });
});
