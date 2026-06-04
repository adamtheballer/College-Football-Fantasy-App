type AutoPickDraftState = {
  status?: string | null;
  isComplete?: boolean | null;
  currentTeamId?: number | null;
  phaseType?: string | null;
};

export const COMPLETED_DRAFT_EXIT_PATH = "/draft";

export const isDraftAutoPickDue = ({
  draftRoom,
  isExpired,
  autoPickPending,
}: {
  draftRoom: AutoPickDraftState | null | undefined;
  isExpired: boolean;
  autoPickPending: boolean;
}) => {
  if (!draftRoom || draftRoom.isComplete || draftRoom.status !== "live") return false;
  if (!draftRoom.currentTeamId || draftRoom.phaseType !== "pick_clock") return false;
  return isExpired && !autoPickPending;
};

export const shouldShowDraftCompletionModal = ({
  isComplete,
  dismissed,
}: {
  isComplete: boolean | null | undefined;
  dismissed: boolean;
}) => Boolean(isComplete && !dismissed);

export const getCompletedDraftExitPath = () => COMPLETED_DRAFT_EXIT_PATH;
