// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";

import {
  getUnauthenticatedEntryPath,
  hasSignedInOnDevice,
  rememberSignedInDevice,
} from "./auth-device";

afterEach(() => localStorage.clear());

describe("known sign-in device routing", () => {
  it("remembers only that this browser previously completed a sign-in", () => {
    expect(hasSignedInOnDevice()).toBe(false);

    rememberSignedInDevice();

    expect(hasSignedInOnDevice()).toBe(true);
    expect(localStorage.length).toBe(1);
  });

  it("sends known devices to sign in without weakening beta access for new devices", () => {
    expect(getUnauthenticatedEntryPath(true, false)).toBe("/login?flow=beta");
    expect(getUnauthenticatedEntryPath(true, true)).toBe("/login");
    expect(getUnauthenticatedEntryPath(false, false)).toBe("/login");
  });
});
