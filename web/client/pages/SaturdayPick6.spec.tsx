import { describe, expect, it } from "vitest";

import type { SaturdayPickPlayer } from "@/hooks/use-saturday-pick";
import { getSaturdayPickRewardMessage, getSaturdayPickSponsorLogo } from "@/lib/saturday-pick-sponsor";

import { displayPoints, lockDeadlineMessage, pickConfirmationMessage, positionLabel, statusLabel } from "./SaturdayPick6";

const player: SaturdayPickPlayer = {
  id: 1,
  player_id: 101,
  canonical_position: "RB",
  player_name: "Ahmad Hardy",
  school: "Missouri",
  opponent: "Arkansas-Pine Bluff",
  game_time: "2026-09-05T16:00:00Z",
  image_url: null,
  projected_points: 18.4,
  live_points: null,
  final_points: null,
  scoring_status: "NOT_STARTED",
  sort_order: 1,
};

describe("SaturdayPick6 state helpers", () => {
  it("uses a live score when available and preserves a missing live score as the projection", () => {
    expect(displayPoints(player, "SCORING")).toBe(18.4);
    expect(displayPoints({ ...player, live_points: 21.6, scoring_status: "LIVE" }, "SCORING")).toBe(21.6);
  });

  it("uses only a final score for a finalized contest", () => {
    expect(displayPoints({ ...player, live_points: 21.6, final_points: 23.1, scoring_status: "FINAL" }, "FINAL")).toBe(23.1);
  });

  it("renders provider states as readable labels", () => {
    expect(statusLabel("DATA_DELAYED")).toBe("DATA DELAYED");
    expect(statusLabel("NOT_STARTED")).toBe("NOT STARTED");
  });

  it("uses the featured position and saved player in the player-facing pick confirmation", () => {
    expect(positionLabel("RB")).toBe("running back");
    expect(positionLabel("TE")).toBe("tight end");
    expect(pickConfirmationMessage("Ahmad Hardy")).toBe("Your pick is in. Follow Ahmad Hardy this Saturday.");
    expect(lockDeadlineMessage("Ahmad Hardy", "2026-09-05T16:00:00Z")).toContain("Ahmad Hardy's game starts at");
    expect(lockDeadlineMessage("Ahmad Hardy", "2026-09-05T16:00:00Z")).toContain("Pick before kickoff; then it will lock.");
  });

  it("uses only the sponsor logo supplied by the API", () => {
    const sponsor = { name: "Example Sponsor", logo_url: null };
    expect(getSaturdayPickSponsorLogo(sponsor)).toBeNull();
    expect(getSaturdayPickRewardMessage(sponsor)).toContain("final scoring");
  });
});
