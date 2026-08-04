import { describe, expect, it } from "vitest";

import { formatProjectionDisplay } from "./projection-display";

describe("formatProjectionDisplay", () => {
  it("keeps verified zero distinct from BYE and a missing projection", () => {
    expect(formatProjectionDisplay(0, "ACTIVE")).toBe("0.0");
    expect(formatProjectionDisplay(null, "BYE")).toBe("BYE");
    expect(formatProjectionDisplay(null, "UNAVAILABLE")).toBe("—");
  });
});
