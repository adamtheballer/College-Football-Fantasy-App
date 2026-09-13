import { describe, expect, it } from "vitest";
import { draftServerNow, isDraftPickExpired, reconcileDraftRoom, stampDraftRoom } from "./draftReconciliation";
import type { DraftRoom } from "@/types/draft";

export const makeRoom = (overrides: Partial<DraftRoom> = {}): DraftRoom => ({
  league_id: 77, draft_id: 5, status: "on_clock", pick_timer_seconds: 30,
  roster_slots: { QB: 1 }, teams: [], picks: [], current_pick: 1, current_round: 1,
  current_round_pick: 1, current_team_id: 1, current_team_name: "Your team",
  user_team_id: 1, can_make_pick: true, can_start_draft: false,
  pre_draft_starts_at: null, draft_starts_at: null, current_pick_started_at: null,
  current_pick_deadline: "2026-09-13T00:00:30Z", transition_ends_at: null,
  seconds_remaining: 30, draft_version: 1, pick_started_at: null, pick_expires_at: null,
  server_time: "2026-09-13T00:00:00Z", ...overrides,
});

describe("authoritative draft reconciliation", () => {
  it("does not rewind version, picks or receipt time on delayed GET or POST", () => {
    const fresh = stampDraftRoom(makeRoom({ draft_version: 3, current_pick: 3 }), 1000);
    const stale = stampDraftRoom(makeRoom(), 5000);
    expect(reconcileDraftRoom(fresh, stale)).toBe(fresh);
    expect(draftServerNow(reconcileDraftRoom(fresh, stale), 6000)).toBe(Date.parse(fresh.server_time) + 5000);
  });
  it("orders equal versions by server time and deduplicates identical snapshots", () => {
    const current = makeRoom();
    expect(reconcileDraftRoom(current, { ...current })).toBe(current);
    const later = makeRoom({ server_time: "2026-09-13T00:00:05Z" });
    expect(reconcileDraftRoom(current, later)).toBe(later);
    expect(reconcileDraftRoom(later, current)).toBe(later);
  });
  it("resets for a new draft but rejects a late response from the prior draft", () => {
    const old = makeRoom({ draft_version: 100 });
    const next = makeRoom({ draft_id: 6 });
    expect(reconcileDraftRoom(old, next, 5)).toBe(next);
    expect(reconcileDraftRoom(next, old, 5)).toBe(next);
  });
  it("checks the exact deadline even between render ticks and fails closed without one", () => {
    const room = stampDraftRoom(makeRoom(), 1000);
    expect(isDraftPickExpired(room, 30_999)).toBe(false);
    expect(isDraftPickExpired(room, 31_000)).toBe(true);
    expect(isDraftPickExpired(room, 31_001)).toBe(true);
    expect(isDraftPickExpired(makeRoom({ current_pick_deadline: null }))).toBe(true);
    expect(isDraftPickExpired(makeRoom({ status: "completed" }))).toBe(false);
  });
});
