const completedGuideKey = (userId: number) => `cfb_completed_guide_${userId}`;
const pendingGuideKey = (userId: number) => `cfb_pending_guide_${userId}`;

export const hasCompletedGuide = (userId: number) =>
  localStorage.getItem(completedGuideKey(userId)) === "true";

export const setCompletedGuide = (userId: number) => {
  localStorage.setItem(completedGuideKey(userId), "true");
  localStorage.removeItem(pendingGuideKey(userId));
};

export const hasPendingGuide = (userId: number) =>
  localStorage.getItem(pendingGuideKey(userId)) === "true";

export const setPendingGuide = (userId: number) => {
  if (!hasCompletedGuide(userId)) {
    localStorage.setItem(pendingGuideKey(userId), "true");
  }
};

export const restartGuide = (userId: number) => {
  localStorage.setItem(pendingGuideKey(userId), "true");
};

export const clearPendingGuide = (userId: number) => {
  localStorage.removeItem(pendingGuideKey(userId));
};
