import { describe, expect, it } from "vitest";

import {
  getMockDraftLobbyPath,
  getMockDraftInvitePath,
  getMockDraftCreateMode,
  getMockDraftCreateSuccessRoomPath,
  getMockDraftResultsPath,
  getMockDraftRoomPath,
  getMockAutoPickDelayMs,
  getMockTurnKey,
  MOCK_DRAFT_EXIT_PATH,
  MOCK_BOT_AUTO_PICK_DELAY_MS,
  shouldShowMockInvitePanel,
  shouldShowMockInviteSuccess,
  shouldShowMockCompletionModal,
  shouldShowSinglePlayerDraftOrderReveal,
  shouldScheduleBotAutoPick,
  shouldTriggerTimerExpiredAutoPick,
  shouldTriggerMockAutoPick,
} from "./mock-draft-flow";

describe("mock draft flow helpers", () => {
  it("builds the standalone mock draft routes", () => {
    expect(getMockDraftLobbyPath(42)).toBe("/draft/mock/42/lobby");
    expect(getMockDraftRoomPath(42)).toBe("/draft/mock/42/room");
    expect(getMockDraftResultsPath(42)).toBe("/draft/mock/42/results");
    expect(getMockDraftInvitePath("secure-token")).toBe("/draft/mock/invite/secure-token");
    expect(MOCK_DRAFT_EXIT_PATH).toBe("/draft");
  });

  it("maps create intent to the backend mock draft mode", () => {
    expect(getMockDraftCreateMode(true)).toBe("single_player");
    expect(getMockDraftCreateMode(false)).toBe("public_multiplayer");
  });

  it("routes single-player create success directly to the room", () => {
    expect(getMockDraftCreateSuccessRoomPath({ mode: "single_player", mock_draft_id: 17 })).toBe("/draft/mock/17/room");
    expect(getMockDraftCreateSuccessRoomPath({ mode: "public_multiplayer", mock_draft_id: 17 })).toBeNull();
  });

  it("shows invite UI only for multiplayer payloads with an invite link", () => {
    expect(shouldShowMockInviteSuccess({ mode: "public_multiplayer", invite_link: "https://example.com/draft/mock/invite/token" })).toBe(true);
    expect(shouldShowMockInviteSuccess({ mode: "single_player", invite_link: null })).toBe(false);
    expect(shouldShowMockInviteSuccess({ mode: "public_multiplayer", invite_link: null })).toBe(false);
    expect(shouldShowMockInvitePanel("public_multiplayer", "https://example.com/draft/mock/invite/token")).toBe(true);
    expect(shouldShowMockInvitePanel("single_player", null)).toBe(false);
    expect(shouldShowMockInvitePanel("public_multiplayer", null)).toBe(false);
  });

  it("triggers auto-pick for bot turns", () => {
    expect(
      shouldTriggerMockAutoPick(
        { status: "live", is_complete: false, current_participant_type: "bot" },
        { isExpired: false, autoPickPending: false }
      )
    ).toBe(true);
  });

  it("schedules bot auto-pick only for a live bot participant", () => {
    expect(
      shouldScheduleBotAutoPick(
        { status: "live", is_complete: false, current_participant_id: 12, current_participant_type: "bot" },
        { autoPickPending: false }
      )
    ).toBe(true);
    expect(
      shouldScheduleBotAutoPick(
        { status: "live", is_complete: false, current_participant_id: 12, current_participant_type: "human" },
        { autoPickPending: false }
      )
    ).toBe(false);
    expect(
      shouldScheduleBotAutoPick(
        { status: "intermission", is_complete: false, current_participant_id: 12, current_participant_type: "bot" },
        { autoPickPending: false }
      )
    ).toBe(false);
  });

  it("uses timer-expired fallback for any live current participant", () => {
    expect(
      shouldTriggerTimerExpiredAutoPick(
        { status: "live", is_complete: false, current_participant_id: 12 },
        { isExpired: true, autoPickPending: false }
      )
    ).toBe(true);
    expect(
      shouldTriggerTimerExpiredAutoPick(
        { status: "live", is_complete: false, current_participant_id: 12 },
        { isExpired: false, autoPickPending: false }
      )
    ).toBe(false);
    expect(
      shouldTriggerTimerExpiredAutoPick(
        { status: "completed", is_complete: true, current_participant_id: 12 },
        { isExpired: true, autoPickPending: false }
      )
    ).toBe(false);
  });

  it("builds a stable turn key from pick and current participant", () => {
    expect(
      getMockTurnKey({
        mock_draft_id: 7,
        current_overall_pick: 1,
        current_participant_id: 44,
        current_participant_type: "bot",
        status: "live",
      } as any)
    ).toBe("7:1:44:bot:live");
  });

  it("uses a short bot delay and immediate human timeout auto-pick", () => {
    expect(getMockAutoPickDelayMs({ current_participant_type: "bot" } as any)).toBe(MOCK_BOT_AUTO_PICK_DELAY_MS);
    expect(getMockAutoPickDelayMs({ current_participant_type: "human" } as any)).toBe(0);
  });

  it("triggers auto-pick for expired human turns only", () => {
    expect(
      shouldTriggerMockAutoPick(
        { status: "live", is_complete: false, current_participant_type: "human" },
        { isExpired: true, autoPickPending: false }
      )
    ).toBe(true);
    expect(
      shouldTriggerMockAutoPick(
        { status: "live", is_complete: false, current_participant_type: "human" },
        { isExpired: false, autoPickPending: false }
      )
    ).toBe(false);
  });

  it("does not auto-pick when complete or pending", () => {
    expect(
      shouldTriggerMockAutoPick(
        { status: "completed", is_complete: true, current_participant_type: null },
        { isExpired: true, autoPickPending: false }
      )
    ).toBe(false);
    expect(
      shouldTriggerMockAutoPick(
        { status: "live", is_complete: false, current_participant_type: "bot" },
        { isExpired: true, autoPickPending: true }
      )
    ).toBe(false);
  });

  it("shows completion modal until the user chooses email or no-thanks", () => {
    expect(shouldShowMockCompletionModal(true, false)).toBe(true);
    expect(shouldShowMockCompletionModal(true, true)).toBe(false);
    expect(shouldShowMockCompletionModal(false, false)).toBe(false);
  });

  it("shows the single-player draft order reveal only during pre-draft countdown", () => {
    expect(
      shouldShowSinglePlayerDraftOrderReveal(
        { status: "intermission", session: { mode: "single_player" } } as any,
        false
      )
    ).toBe(true);
    expect(
      shouldShowSinglePlayerDraftOrderReveal(
        { status: "live", session: { mode: "single_player" } } as any,
        false
      )
    ).toBe(false);
    expect(
      shouldShowSinglePlayerDraftOrderReveal(
        { status: "intermission", session: { mode: "public_multiplayer" } } as any,
        false
      )
    ).toBe(false);
    expect(
      shouldShowSinglePlayerDraftOrderReveal(
        { status: "intermission", session: { mode: "single_player" } } as any,
        true
      )
    ).toBe(false);
  });
});
