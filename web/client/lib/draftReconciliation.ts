import type { DraftRoom } from "@/types/draft";

// Receipt time belongs to the snapshot, not to Query's dataUpdatedAt: a rejected
// stale response can update Query metadata without updating authoritative data.
const receivedAt = new WeakMap<DraftRoom, number>();

export function stampDraftRoom(room: DraftRoom, now = Date.now()) {
  receivedAt.set(room, now);
  return room;
}

export function draftServerNow(room: DraftRoom, now = Date.now()) {
  const receipt = receivedAt.get(room);
  return receipt === undefined ? now : Date.parse(room.server_time) + Math.max(0, now - receipt);
}

export function draftSnapshotAge(room: DraftRoom, now = Date.now()) {
  return Math.max(0, now - (receivedAt.get(room) ?? now));
}

export function reconcileDraftRoom(
  current: DraftRoom | undefined,
  incoming: DraftRoom,
  requestDraftId?: number,
): DraftRoom {
  if (!current) return incoming;
  if (current.draft_id !== incoming.draft_id) {
    // A request started for a previous draft must not resurrect it after reset.
    return requestDraftId !== undefined && current.draft_id !== requestDraftId ? current : incoming;
  }
  if (incoming.draft_version < current.draft_version) return current;
  if (incoming.draft_version === current.draft_version &&
      Date.parse(incoming.server_time) <= Date.parse(current.server_time)) return current;
  return incoming;
}

export function isDraftPickExpired(room: DraftRoom, now = Date.now()) {
  const deadline = Date.parse(room.current_pick_deadline ?? "");
  return room.status === "on_clock" &&
    (!Number.isFinite(deadline) || draftServerNow(room, now) >= deadline);
}
