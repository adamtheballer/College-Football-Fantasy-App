import { describe, expect, it } from "vitest";

import {
  isWaiverClaimEditable,
  isWaiverClaimProcessingOverdue,
  scheduledTimeForWaiverClaim,
} from "@/lib/waiverTiming";

const pendingClaim = {
  status: "pending",
  waiver_period_id: 42,
  process_after: "2026-07-22T12:00:00Z",
};

describe("waiver claim timing", () => {
  it("uses the current durable period time over a legacy claim timestamp", () => {
    expect(
      scheduledTimeForWaiverClaim(pendingClaim, {
        id: 42,
        processes_at: "2026-07-28T12:00:00Z",
      })
    ).toBe("2026-07-28T12:00:00Z");
  });

  it("marks an overdue pending claim as delayed and not editable", () => {
    const now = Date.parse("2026-07-25T12:00:00Z");

    expect(isWaiverClaimProcessingOverdue(pendingClaim, null, now)).toBe(true);
    expect(isWaiverClaimEditable(pendingClaim, null, now)).toBe(false);
  });

  it("keeps a pending claim editable before its processing time", () => {
    const now = Date.parse("2026-07-25T12:00:00Z");
    const period = { id: 42, processes_at: "2026-07-28T12:00:00Z" };

    expect(isWaiverClaimProcessingOverdue(pendingClaim, period, now)).toBe(false);
    expect(isWaiverClaimEditable(pendingClaim, period, now)).toBe(true);
  });
});
