import { describe, expect, it } from "vitest";

import {
  PASSWORD_POLICY_MESSAGE,
  passwordMeetsPolicy,
  validatePasswordChange,
} from "./password-policy";

describe("password policy", () => {
  it("requires every shared password rule", () => {
    expect(passwordMeetsPolicy("StrongPass123!")).toBe(true);
    expect(passwordMeetsPolicy("lowercase123!")).toBe(false);
    expect(passwordMeetsPolicy("UPPERCASE123!")).toBe(false);
    expect(passwordMeetsPolicy("NoNumberPassword!")).toBe(false);
    expect(passwordMeetsPolicy("NoSpecialPassword123")).toBe(false);
    expect(passwordMeetsPolicy("A".repeat(130) + "a1!")).toBe(false);
    expect(PASSWORD_POLICY_MESSAGE).toContain("12–128");
  });

  it("requires matching replacement passwords and a current password", () => {
    expect(validatePasswordChange("", "StrongPass123!", "StrongPass123!")).toContain("Complete");
    expect(validatePasswordChange("OldPass123!", "StrongPass123!", "DifferentPass123!")).toContain("match");
    expect(validatePasswordChange("OldPass123!", "StrongPass123!", "StrongPass123!")).toBeNull();
  });
});
