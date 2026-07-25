import type { LeagueWaiverClaim, LeagueWaiverPeriod } from "@/types/league";

type WaiverClaimTiming = Pick<
  LeagueWaiverClaim,
  "status" | "waiver_period_id" | "process_after"
>;
type WaiverPeriodTiming = Pick<LeagueWaiverPeriod, "id" | "processes_at">;

export function scheduledTimeForWaiverClaim(
  claim: Pick<LeagueWaiverClaim, "waiver_period_id" | "process_after">,
  currentPeriod?: WaiverPeriodTiming | null
): string | null {
  if (currentPeriod?.id === claim.waiver_period_id) {
    return currentPeriod.processes_at;
  }

  return claim.process_after;
}

export function isWaiverClaimProcessingOverdue(
  claim: WaiverClaimTiming,
  currentPeriod?: WaiverPeriodTiming | null,
  now = Date.now()
): boolean {
  if (claim.status.toLowerCase() !== "pending") {
    return false;
  }

  const scheduledFor = scheduledTimeForWaiverClaim(claim, currentPeriod);
  if (!scheduledFor) {
    return false;
  }

  const scheduledAt = Date.parse(scheduledFor);
  return !Number.isNaN(scheduledAt) && scheduledAt <= now;
}

export function isWaiverClaimEditable(
  claim: WaiverClaimTiming,
  currentPeriod?: WaiverPeriodTiming | null,
  now = Date.now()
): boolean {
  return !isWaiverClaimProcessingOverdue(claim, currentPeriod, now);
}
