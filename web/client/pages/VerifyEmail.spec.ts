import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { verificationErrorMessage } from "./VerifyEmail";

describe("verificationErrorMessage", () => {
  it("turns expired verification token errors into user-actionable copy", () => {
    expect(verificationErrorMessage(new ApiError(400, "expired token"))).toContain(
      "expired"
    );
    expect(verificationErrorMessage(new ApiError(400, "expired token"))).toContain(
      "Request a new verification email"
    );
  });

  it("distinguishes invalid and already-used token states", () => {
    expect(verificationErrorMessage(new ApiError(400, "invalid token"))).toContain("invalid");
    expect(verificationErrorMessage(new ApiError(400, "token already used"))).toContain(
      "already used"
    );
  });

  it("keeps rate-limit failures actionable", () => {
    expect(verificationErrorMessage(new ApiError(429, "too many requests"))).toContain(
      "Too many verification attempts"
    );
  });

  it("keeps backend reachability failures specific", () => {
    expect(verificationErrorMessage(new ApiError(0, "network failed"))).toContain(
      "Unable to reach the backend API"
    );
  });
});
