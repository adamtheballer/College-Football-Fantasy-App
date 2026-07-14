import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { passwordResetErrorMessage, validateNewPassword } from "./PasswordResetConfirm";

describe("PasswordResetConfirm helpers", () => {
  it("validates the public password policy before submit", () => {
    expect(validateNewPassword("short", "short")).toContain("at least 12");
    expect(validateNewPassword("lowercase123!", "lowercase123!")).toContain("uppercase");
    expect(validateNewPassword("NoNumberHere!", "NoNumberHere!")).toContain("number");
    expect(validateNewPassword("NoSpecial123", "NoSpecial123")).toContain("special");
    expect(validateNewPassword("StrongPass123!", "DifferentPass123!")).toContain("do not match");
    expect(validateNewPassword("StrongPass123!", "StrongPass123!")).toBeNull();
  });

  it("keeps reset API failures user-actionable", () => {
    expect(passwordResetErrorMessage(new ApiError(400, "expired token"))).toContain("invalid, expired, or already used");
    expect(passwordResetErrorMessage(new ApiError(429, "too many requests"))).toContain("Too many reset attempts");
    expect(passwordResetErrorMessage(new ApiError(0, "network failed"))).toContain("Unable to reach the backend API");
  });
});
