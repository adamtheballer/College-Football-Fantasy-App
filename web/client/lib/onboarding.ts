const completedGuideKey = (userId: number) => `cfb_completed_guide_${userId}`;
const pendingGuideKey = (userId: number) => `cfb_pending_guide_${userId}`;

const safeGet = (key: string) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeSet = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Ignore storage errors to avoid crashing app boot.
  }
};

const safeRemove = (key: string) => {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage errors to avoid crashing app boot.
  }
};

export const hasCompletedGuide = (userId: number) =>
  safeGet(completedGuideKey(userId)) === "true";

export const setCompletedGuide = (userId: number) => {
  safeSet(completedGuideKey(userId), "true");
  safeRemove(pendingGuideKey(userId));
};

export const hasPendingGuide = (userId: number) =>
  safeGet(pendingGuideKey(userId)) === "true";

export const setPendingGuide = (userId: number) => {
  if (!hasCompletedGuide(userId)) {
    safeSet(pendingGuideKey(userId), "true");
  }
};

export const restartGuide = (userId: number) => {
  safeSet(pendingGuideKey(userId), "true");
};

export const clearPendingGuide = (userId: number) => {
  safeRemove(pendingGuideKey(userId));
};
