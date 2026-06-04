import { useEffect, useMemo, useState } from "react";

export function formatDraftTime(totalSeconds: number) {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function calculateDraftSecondsRemaining(
  serverTime: string | null | undefined,
  currentPickExpiresAt: string | null | undefined,
  clientNowMs = Date.now()
) {
  if (!serverTime || !currentPickExpiresAt) return 0;
  const serverMs = Date.parse(serverTime);
  const expiresMs = Date.parse(currentPickExpiresAt);
  if (!Number.isFinite(serverMs) || !Number.isFinite(expiresMs)) return 0;
  const offsetMs = serverMs - clientNowMs;
  const correctedNowMs = clientNowMs + offsetMs;
  return Math.max(0, Math.ceil((expiresMs - correctedNowMs) / 1000));
}

export function calculateClientServerOffset(serverTime: string | null | undefined, clientNowMs = Date.now()) {
  if (!serverTime) return 0;
  const serverMs = Date.parse(serverTime);
  if (!Number.isFinite(serverMs)) return 0;
  return serverMs - clientNowMs;
}

export function calculateDraftSecondsRemainingWithOffset(
  currentPickExpiresAt: string | null | undefined,
  clientServerOffsetMs: number,
  clientNowMs = Date.now()
) {
  if (!currentPickExpiresAt) return 0;
  const expiresMs = Date.parse(currentPickExpiresAt);
  if (!Number.isFinite(expiresMs)) return 0;
  const correctedNowMs = clientNowMs + clientServerOffsetMs;
  return Math.max(0, Math.ceil((expiresMs - correctedNowMs) / 1000));
}

export function useDraftTimer({
  serverTime,
  currentPickExpiresAt,
  currentPick,
}: {
  serverTime?: string | null;
  currentPickExpiresAt?: string | null;
  currentPick?: number | null;
}) {
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    calculateDraftSecondsRemaining(serverTime, currentPickExpiresAt)
  );

  useEffect(() => {
    const offsetMs = calculateClientServerOffset(serverTime);
    const updateSecondsRemaining = () => {
      setSecondsRemaining(calculateDraftSecondsRemainingWithOffset(currentPickExpiresAt, offsetMs));
    };

    updateSecondsRemaining();
    if (!serverTime || !currentPickExpiresAt) return;
    const interval = window.setInterval(() => {
      updateSecondsRemaining();
    }, 1_000);
    return () => window.clearInterval(interval);
  }, [serverTime, currentPickExpiresAt, currentPick]);

  return useMemo(
    () => ({
      secondsRemaining,
      formattedTime: formatDraftTime(secondsRemaining),
      isExpired: secondsRemaining <= 0,
    }),
    [secondsRemaining]
  );
}
