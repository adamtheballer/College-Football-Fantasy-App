export type PendingPushTap = { eventId: number; recipientId: number; receivedAt: number };
const storageKey = "cffb_pending_push_tap";
let pending: PendingPushTap | null = null;
const positiveId = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value > 0;
export function queuePushTap(data: Record<string, unknown> | undefined): void {
  if (!data || !positiveId(data.event_id) || !positiveId(data.recipient_user_id)) return;
  pending = { eventId: data.event_id, recipientId: data.recipient_user_id, receivedAt: Date.now() };
  try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch { /* Memory retains the tap. */ }
  window.dispatchEvent(new Event("cffb-push-tap"));
}
export function readPendingPushTap(): PendingPushTap | null {
  if (!pending) {
    try {
      const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
      if (value && positiveId(value.eventId) && positiveId(value.recipientId) && typeof value.receivedAt === "number") pending = value;
    } catch { /* Ignore malformed persisted input. */ }
  }
  if (pending && (Date.now() - pending.receivedAt > 10 * 60_000 || pending.receivedAt > Date.now() + 60_000)) clearPendingPushTap();
  return pending;
}
export function clearPendingPushTap(): void {
  pending = null;
  try { sessionStorage.removeItem(storageKey); } catch { /* Memory remains cleared. */ }
}
