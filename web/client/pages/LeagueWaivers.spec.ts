import { describe, expect, it } from "vitest";

import { waiverProjectionLabel } from "./LeagueWaivers";

describe("waiverProjectionLabel", () => {
  it("uses the backend projection status instead of presenting a bye as a missing projection", () => {
    expect(waiverProjectionLabel(0, "BYE")).toBe("BYE");
    expect(waiverProjectionLabel(0, "OUT")).toBe("OUT");
    expect(waiverProjectionLabel(12.34, "ACTIVE")).toBe("12.3");
    expect(waiverProjectionLabel(undefined, "UNAVAILABLE")).toBe("—");
  });
});
