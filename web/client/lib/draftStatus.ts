export type DraftCountdownParts = {
  totalMs: number;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
};

export const getDraftTimeMs = (draftDateTime?: string | Date | null) => {
  if (!draftDateTime) return null;
  const value = draftDateTime instanceof Date ? draftDateTime : new Date(draftDateTime);
  const time = value.getTime();
  return Number.isFinite(time) ? time : null;
};

export const hasDraftStarted = (
  draftDateTime?: string | Date | null,
  now = Date.now(),
) => {
  const draftTimeMs = getDraftTimeMs(draftDateTime);
  return draftTimeMs !== null && draftTimeMs <= now;
};

export const canJoinDraftRoom = ({
  draftDateTime,
  memberCount,
  maxTeams,
  now = Date.now(),
}: {
  draftDateTime?: string | Date | null;
  memberCount: number;
  maxTeams: number;
  now?: number;
}) => {
  return memberCount >= maxTeams && hasDraftStarted(draftDateTime, now);
};

export const getDraftCountdownParts = (
  draftDateTime?: string | Date | null,
  now = Date.now(),
): DraftCountdownParts | null => {
  const draftTimeMs = getDraftTimeMs(draftDateTime);
  if (draftTimeMs === null) return null;

  const totalMs = Math.max(0, draftTimeMs - now);
  const totalSeconds = Math.floor(totalMs / 1_000);
  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;

  return { totalMs, days, hours, minutes, seconds };
};

export const formatDraftCountdown = (
  draftDateTime?: string | Date | null,
  now = Date.now(),
) => {
  const parts = getDraftCountdownParts(draftDateTime, now);
  if (!parts) return "Draft not scheduled";
  if (parts.totalMs <= 0) return "Draft room open";
  return `${parts.days}d ${parts.hours}h ${parts.minutes}m ${parts.seconds}s`;
};
