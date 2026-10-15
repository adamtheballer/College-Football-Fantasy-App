export type NameChangeEligibility = {
  account_id: number;
  current_name: string;
  server_time: string;
  last_successful_change_at: string | null;
  next_eligible_at: string | null;
  remaining_wait_seconds: number;
  can_change_name: boolean;
};

export function isNameChangeEligibility(value: unknown): value is NameChangeEligibility {
  if (!value || typeof value !== "object") return false;
  const v = value as Partial<NameChangeEligibility>;
  return typeof v.account_id === "number" && typeof v.current_name === "string" &&
    typeof v.server_time === "string" && Number.isFinite(Date.parse(v.server_time)) &&
    (v.next_eligible_at === null || (typeof v.next_eligible_at === "string" && Number.isFinite(Date.parse(v.next_eligible_at)))) &&
    (v.last_successful_change_at === null || (typeof v.last_successful_change_at === "string" && Number.isFinite(Date.parse(v.last_successful_change_at)))) &&
    typeof v.remaining_wait_seconds === "number" && Number.isFinite(v.remaining_wait_seconds) && v.remaining_wait_seconds >= 0 &&
    typeof v.can_change_name === "boolean" && (v.can_change_name || (v.next_eligible_at !== null && v.remaining_wait_seconds > 0));
}

export function nameChangeRemainingMs(timing: NameChangeEligibility): number {
  return timing.next_eligible_at ? Math.max(0, Date.parse(timing.next_eligible_at) - Date.parse(timing.server_time)) : 0;
}

export function formatNameChangeWait(seconds: number): string {
  if (seconds < 60) return "less than a minute";
  const minutes = Math.ceil(seconds / 60);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const remainingMinutes = minutes % 60;
  const pieces = [[days, "day"], [hours, "hour"], [remainingMinutes, "minute"]] as const;
  const labels = pieces.filter(([amount]) => amount > 0).map(([amount, label]) => `${amount} ${label}${amount === 1 ? "" : "s"}`);
  if (labels.length < 2) return labels[0];
  return `${labels.slice(0, -1).join(", ")}${labels.length > 2 ? "," : ""} and ${labels.at(-1)}`;
}
