import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { loginErrorMessage } from "./Login";

describe("loginErrorMessage", () => {
  it("maps invalid credentials to direct copy", () => {
    expect(loginErrorMessage(new ApiError(401, "invalid credentials"))).toBe(
      "Email or password is incorrect."
    );
  });

  it("maps account lockout separately from invalid credentials", () => {
    expect(loginErrorMessage(new ApiError(423, "account temporarily locked"))).toBe(
      "This account is temporarily locked after too many failed attempts. Try again later or reset your password."
    );
  });

  it("maps rate limits and backend reachability failures", () => {
    expect(loginErrorMessage(new ApiError(429, "too many requests"))).toBe(
      "Too many sign-in attempts. Wait a few minutes and try again."
    );
    expect(loginErrorMessage(new ApiError(0, "network failed"))).toContain(
      "Local API is unavailable"
    );
  });

  it("keeps validation and service errors actionable", () => {
    expect(loginErrorMessage(new ApiError(422, "email: value is not a valid email"))).toBe(
      "email: value is not a valid email"
    );
    expect(loginErrorMessage(new ApiError(500, "database unavailable"))).toBe(
      "The sign-in service hit an error. Try again or contact support."
    );
  });
});
