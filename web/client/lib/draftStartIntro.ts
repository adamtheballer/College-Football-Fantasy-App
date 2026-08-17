export const DRAFT_START_INTRO_AUDIO_URL = "/audio/cfb-draft-start-intro.wav";

export type DraftStartIntroState = {
  draftId: number | null | undefined;
  status: string | null | undefined;
  currentPick: number | null | undefined;
  currentPickStartedAt: string | null | undefined;
};

/**
 * The intro is deliberately anchored to the authoritative first-pick timer,
 * rather than a client clock or a draft-room page load.  The real Draft route
 * is the only consumer of this guard; mock drafts never import it.
 */
export const isFirstLiveDraftPick = ({
  draftId,
  status,
  currentPick,
  currentPickStartedAt,
}: DraftStartIntroState) =>
  typeof draftId === "number" &&
  status?.trim().toLowerCase() === "on_clock" &&
  currentPick === 1 &&
  Boolean(currentPickStartedAt);

export const getDraftStartIntroCueKey = ({
  draftId,
  currentPickStartedAt,
}: Pick<DraftStartIntroState, "draftId" | "currentPickStartedAt">) =>
  `cfb:draft-start-intro:${draftId ?? "unknown"}:${currentPickStartedAt ?? "unknown"}`;

export const didFirstLiveDraftPickStart = (
  previous: DraftStartIntroState | null,
  current: DraftStartIntroState,
) => previous !== null && !isFirstLiveDraftPick(previous) && isFirstLiveDraftPick(current);
