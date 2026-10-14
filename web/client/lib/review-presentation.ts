let blockers = 0;
const listeners = new Set<() => void>();
export const hasReviewPresentationBlocker = () => blockers > 0;
export const observeReviewPresentation = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};
/** Covers a system permission request before UIKit has presented its UI. */
export async function withReviewPresentationBlocker<T>(work: () => Promise<T>): Promise<T> {
  blockers++;
  listeners.forEach((listener) => listener());
  try { return await work(); }
  finally { blockers--; listeners.forEach((listener) => listener()); }
}
