import { afterEach, describe, expect, it, vi } from "vitest";

import {
  LOCALHOST_INVITE_WARNING,
  copyInviteLinkToClipboard,
  extractMockInviteToken,
  getInviteLinkStatus,
  isLocalhostUrl,
} from "./url";

describe("public invite URL helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("detects localhost invite links", () => {
    expect(isLocalhostUrl("http://localhost:8080/draft/mock/invite/token")).toBe(true);
    expect(isLocalhostUrl("http://127.0.0.1:8080/draft/mock/invite/token")).toBe(true);
    expect(isLocalhostUrl("http://0.0.0.0:8080/draft/mock/invite/token")).toBe(true);
  });

  it("shows local-only warning for localhost invite links", () => {
    const status = getInviteLinkStatus("http://localhost:8080/draft/mock/invite/token");

    expect(status.label).toBe("Local-only link");
    expect(status.isLocalOnly).toBe(true);
    expect(status.warning).toBe(LOCALHOST_INVITE_WARNING);
  });

  it("shows public-ready status for public invite links", () => {
    const status = getInviteLinkStatus("https://frontend-tunnel.example/draft/mock/invite/token");

    expect(status.label).toBe("Public invite link ready");
    expect(status.isLocalOnly).toBe(false);
    expect(status.warning).toBeNull();
  });

  it("copies the full invite URL", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(copyInviteLinkToClipboard("https://frontend-tunnel.example/draft/mock/invite/full-token")).resolves.toBe(true);

    expect(writeText).toHaveBeenCalledWith("https://frontend-tunnel.example/draft/mock/invite/full-token");
  });

  it("extracts mock invite tokens from pasted links and legacy query links", () => {
    expect(extractMockInviteToken("https://frontend-tunnel.example/draft/mock/invite/secure-token")).toBe("secure-token");
    expect(extractMockInviteToken("http://localhost:8080/draft/mock/join?code=legacy-token")).toBe("legacy-token");
    expect(extractMockInviteToken("plain-token")).toBe("plain-token");
  });
});
