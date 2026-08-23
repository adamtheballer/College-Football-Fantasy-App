export const DRAFT_AUDIO_URLS = {
  start: "/audio/cfb-draft-start.wav",
  userFirstPick: "/audio/cfb-draft-user-first-pick.wav",
  userCountdown: "/audio/cfb-draft-user-countdown-10.wav",
} as const;

export type DraftAudioCue = keyof typeof DRAFT_AUDIO_URLS;

export type DraftAudioState = {
  draftId: number | null | undefined;
  status: string | null | undefined;
  currentPick: number | null | undefined;
  currentPickStartedAt: string | null | undefined;
  currentTeamId: number | null | undefined;
  userTeamId: number | null | undefined;
};

const isLivePick = ({ draftId, status, currentPick, currentPickStartedAt }: DraftAudioState) =>
  typeof draftId === "number" &&
  status?.trim().toLowerCase() === "on_clock" &&
  typeof currentPick === "number" &&
  currentPick > 0 &&
  Boolean(currentPickStartedAt);

export const isFirstLiveDraftPick = (state: DraftAudioState) =>
  isLivePick(state) && state.currentPick === 1;

export const isActiveUserPick = (state: DraftAudioState) =>
  isLivePick(state) &&
  typeof state.currentTeamId === "number" &&
  state.currentTeamId === state.userTeamId;

export const getDraftAudioCueKey = (
  cue: DraftAudioCue,
  { draftId, currentPick, currentPickStartedAt }: Pick<DraftAudioState, "draftId" | "currentPick" | "currentPickStartedAt">,
) =>
  `cfb:draft-audio:${cue}:${draftId ?? "unknown"}:${currentPick ?? "unknown"}:${currentPickStartedAt ?? "unknown"}`;

const getLivePickKey = ({ draftId, currentPick, currentPickStartedAt }: DraftAudioState) =>
  `${draftId ?? "unknown"}:${currentPick ?? "unknown"}:${currentPickStartedAt ?? "unknown"}`;

/**
 * Server state is polled once per second. A cue must only fire when the page
 * observes a new live pick, never merely because it rendered or reconnected.
 */
export const didLivePickStart = (previous: DraftAudioState | null, current: DraftAudioState) =>
  previous !== null &&
  isLivePick(current) &&
  (!isLivePick(previous) || getLivePickKey(previous) !== getLivePickKey(current));

export const shouldPlayDraftStartCue = (previous: DraftAudioState | null, current: DraftAudioState) =>
  previous !== null && didLivePickStart(previous, current) && isFirstLiveDraftPick(current);

/**
 * The first overall pick already has the draft-start cue. Even if it belongs
 * to the viewer, never add a second cue on top of it.
 */
export const shouldPlayUserFirstPickCue = ({
  previous,
  current,
  completedUserPickCount,
}: {
  previous: DraftAudioState | null;
  current: DraftAudioState;
  completedUserPickCount: number;
}) =>
  previous !== null &&
  didLivePickStart(previous, current) &&
  isActiveUserPick(current) &&
  completedUserPickCount === 0 &&
  current.currentPick !== 1;

export const shouldPlayUserCountdownCue = ({
  current,
  secondsRemaining,
}: {
  current: DraftAudioState;
  secondsRemaining: number;
}) => isActiveUserPick(current) && secondsRemaining === 10;
