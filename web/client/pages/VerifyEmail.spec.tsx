import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getVerifyEmailToken,
  resendVerificationRequest,
  verifyEmailTokenRequest,
} from "./VerifyEmail";
import { apiPost } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  apiPost: vi.fn(),
}));

describe("VerifyEmail", () => {
  beforeEach(() => {
    vi.mocked(apiPost).mockReset();
  });

  it("reads the verification token from the query string", () => {
    expect(getVerifyEmailToken("?token=abc123")).toBe("abc123");
    expect(getVerifyEmailToken("?next=/&token=%20abc123%20")).toBe("abc123");
    expect(getVerifyEmailToken("?missing=true")).toBe("");
  });

  it("posts the verification token to the public auth endpoint", async () => {
    vi.mocked(apiPost).mockResolvedValue({ message: "email verified" });

    await expect(verifyEmailTokenRequest("verify-token")).resolves.toMatchObject({
      message: "email verified",
    });

    expect(apiPost).toHaveBeenCalledWith("/auth/verify-email", { token: "verify-token" });
  });

  it("posts resend verification requests by email", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      message: "if an account needs verification, a new email was sent",
    });

    await expect(resendVerificationRequest("coach@example.com")).resolves.toMatchObject({
      message: "if an account needs verification, a new email was sent",
    });

    expect(apiPost).toHaveBeenCalledWith("/auth/resend-verification", {
      email: "coach@example.com",
    });
  });
});
