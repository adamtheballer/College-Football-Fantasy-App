const DRAFT_COMPLETE_STATUSES = new Set([
  "complete",
  "completed",
  "draft_completed",
  "post_draft",
  "final",
  "closed",
]);

export const normalizeLifecycleStatus = (status?: string | null) =>
  (status || "").trim().toLowerCase();

export const isLeaguePostDraft = ({
  draftStatus,
  leagueStatus,
}: {
  draftStatus?: string | null;
  leagueStatus?: string | null;
}) => {
  const normalizedDraftStatus = normalizeLifecycleStatus(draftStatus);
  const normalizedLeagueStatus = normalizeLifecycleStatus(leagueStatus);
  return DRAFT_COMPLETE_STATUSES.has(normalizedDraftStatus) || DRAFT_COMPLETE_STATUSES.has(normalizedLeagueStatus);
};

export const shouldRestrictLeagueToDraft = ({
  draftStatus,
  leagueStatus,
}: {
  draftStatus?: string | null;
  leagueStatus?: string | null;
}) => !isLeaguePostDraft({ draftStatus, leagueStatus });
