import { describe, expect, it } from "vitest";

import {
  BETA_ACCESS_CODE_PREFIX,
  betaAccessCodeFromSuffix,
  normalizeBetaAccessCodeSuffix,
} from "./beta-access";

describe("beta access code input", () => {
  it("keeps the shared prefix out of editable field state", () => {
    expect(normalizeBetaAccessCodeSuffix("a1b2c3")).toBe("A1B2C3");
    expect(betaAccessCodeFromSuffix("a1b2c3")).toBe(
      `${BETA_ACCESS_CODE_PREFIX}A1B2C3`,
    );
  });

  it("accepts a pasted full code without duplicating the prefix", () => {
    expect(normalizeBetaAccessCodeSuffix(" early-a1b2c3 ")).toBe("A1B2C3");
    expect(betaAccessCodeFromSuffix("EARLY-A1B2C3")).toBe("EARLY-A1B2C3");
  });
});
