export const AUTH_CHANGED_EVENT = "cfb-auth-changed";
export const AUTH_EXPIRED_EVENT = "cfb-auth-expired";

export const dispatchAuthChanged = () => {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
};

export const dispatchAuthExpired = () => {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  dispatchAuthChanged();
};
