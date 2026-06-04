import type { StandaloneMockDraftCreateResponse, StandaloneMockDraftMode, StandaloneMockDraftRoom } from "@/types/mock-draft";

export const getMockDraftLobbyPath = (mockDraftId: number) => `/draft/mock/${mockDraftId}/lobby`;
export const getMockDraftRoomPath = (mockDraftId: number) => `/draft/mock/${mockDraftId}/room`;
export const getMockDraftResultsPath = (mockDraftId: number) => `/draft/mock/${mockDraftId}/results`;
export const getMockDraftInvitePath = (inviteToken: string) => `/draft/mock/invite/${encodeURIComponent(inviteToken)}`;
export const MOCK_DRAFT_EXIT_PATH = "/draft";

export const getMockDraftCreateMode = (isSinglePlayerIntent: boolean): StandaloneMockDraftMode =>
  isSinglePlayerIntent ? "single_player" : "public_multiplayer";

export function getMockDraftCreateSuccessRoomPath(payload: Pick<StandaloneMockDraftCreateResponse, "mode" | "mock_draft_id">) {
  return payload.mode === "single_player" ? getMockDraftRoomPath(payload.mock_draft_id) : null;
}

export function shouldShowMockInviteSuccess(
  payload: Pick<StandaloneMockDraftCreateResponse, "mode" | "invite_link"> | null | undefined
): payload is StandaloneMockDraftCreateResponse & { mode: "public_multiplayer"; invite_link: string } {
  return Boolean(payload?.mode === "public_multiplayer" && payload.invite_link);
}

export function shouldShowMockInvitePanel(mode: StandaloneMockDraftMode | null | undefined, inviteLink: string | null | undefined) {
  return Boolean(mode === "public_multiplayer" && inviteLink);
}

export function shouldTriggerMockAutoPick(
  room: Pick<StandaloneMockDraftRoom, "status" | "is_complete" | "current_participant_type"> | null | undefined,
  options: { isExpired: boolean; autoPickPending: boolean }
) {
  if (!room || room.status !== "live" || room.is_complete || options.autoPickPending) return false;
  if (room.current_participant_type === "bot") return true;
  return options.isExpired;
}

export function shouldShowMockCompletionModal(isComplete: boolean, choiceMade: boolean) {
  return Boolean(isComplete && !choiceMade);
}
