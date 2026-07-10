import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { verificationErrorMessage } from "./VerifyEmail";

describe("verificationErrorMessage", () => {
  it("turns expired verification token errors into user-actionable copy", () => {
    expect(verificationErrorMessage(new ApiError(400, "invalid or expired token"))).toContain(
      "invalid or expired"
    );
    expect(verificationErrorMessage(new ApiError(400, "invalid or expired token"))).toContain(
      "Request a new verification email"
    );
  });

  it("keeps backend reachability failures specific", () => {
    expect(verificationErrorMessage(new ApiError(0, "network failed"))).toContain(
      "Unable to reach the backend API"
    );
  });
});
