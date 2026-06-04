import { describe, expect, it } from "vitest";

import {
  getMockDraftLobbyPath,
  getMockDraftInvitePath,
  getMockDraftCreateMode,
  getMockDraftCreateSuccessRoomPath,
  getMockDraftResultsPath,
  getMockDraftRoomPath,
  MOCK_DRAFT_EXIT_PATH,
  shouldShowMockInvitePanel,
  shouldShowMockInviteSuccess,
  shouldShowMockCompletionModal,
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
});
