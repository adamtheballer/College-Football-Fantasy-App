import { describe, expect, it } from "vitest";

import { getDraftPlayerPoolBackendLimit, getDraftPlayerPoolPageOffsets } from "./use-players";

describe("getDraftPlayerPoolBackendLimit", () => {
  it("never exceeds the backend /players API page limit", () => {
    expect(getDraftPlayerPoolBackendLimit(200)).toBe(100);
    expect(getDraftPlayerPoolBackendLimit(100)).toBe(100);
    expect(getDraftPlayerPoolBackendLimit(12)).toBe(12);
  });
});

describe("getDraftPlayerPoolPageOffsets", () => {
  it("keeps finite page loading when fetchAll is not requested", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: false,
        limit: 100,
        offset: 0,
        pages: 5,
        total: 1200,
      })
    ).toEqual([0, 100, 200, 300, 400]);
  });

  it("loads every page needed for the full draft pool when fetchAll is requested", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: getDraftPlayerPoolBackendLimit(200),
        offset: 0,
        total: 1200,
      })
    ).toEqual([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100]);
  });

  it("splits a 200-player draft board request into valid 100-row backend pages", () => {
    const backendLimit = getDraftPlayerPoolBackendLimit(200);

    expect(backendLimit).toBe(100);
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: backendLimit,
        offset: 0,
        total: 201,
      })
    ).toEqual([0, 100, 200]);
  });

  it("caps fetchAll requests to prevent runaway page loading", () => {
    expect(
      getDraftPlayerPoolPageOffsets({
        fetchAll: true,
        limit: 100,
        maxPages: 3,
        offset: 0,
        total: 1200,
      })
    ).toEqual([0, 100, 200]);
  });
});
