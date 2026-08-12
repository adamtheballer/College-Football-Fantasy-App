import { describe, expect, it } from "vitest";

import type { SaturdayPickPlayer } from "@/hooks/use-saturday-pick";
import {
  getSaturdayPickRewardMessage,
  getSaturdayPickSponsorLogo,
} from "@/lib/saturday-pick-sponsor";

import {
  displayPoints,
  isSaturdayPick6ComingSoon,
  lockDeadlineMessage,
  pickConfirmationMessage,
  positionLabel,
  SATURDAY_PICK_6_COMING_SOON_MESSAGE,
  SATURDAY_PICK_6_HOW_IT_WORKS,
  shouldRevealSponsorReward,
  statusLabel,
} from "./SaturdayPick6";

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
  it("explains the weekly pick and winner reward without promising a code before results finalize", () => {
    expect(SATURDAY_PICK_6_HOW_IT_WORKS).toContain("six featured players");
    expect(SATURDAY_PICK_6_HOW_IT_WORKS).toContain("first kickoff");
    expect(SATURDAY_PICK_6_HOW_IT_WORKS).toContain(
      "most fantasy points that week",
    );
    expect(SATURDAY_PICK_6_HOW_IT_WORKS).toContain("discount code");
    expect(SATURDAY_PICK_6_HOW_IT_WORKS).toMatch(/^How it works: Choose /);
  });

  it("uses a live score when available and preserves a missing live score as the projection", () => {
    expect(displayPoints(player, "SCORING")).toBe(18.4);
    expect(
      displayPoints(
        { ...player, live_points: 21.6, scoring_status: "LIVE" },
        "SCORING",
      ),
    ).toBe(21.6);
  });

  it("uses only a final score for a finalized contest", () => {
    expect(
      displayPoints(
        {
          ...player,
          live_points: 21.6,
          final_points: 23.1,
          scoring_status: "FINAL",
        },
        "FINAL",
      ),
    ).toBe(23.1);
  });

  it("renders provider states as readable labels", () => {
    expect(statusLabel("DATA_DELAYED")).toBe("DATA DELAYED");
    expect(statusLabel("NOT_STARTED")).toBe("NOT STARTED");
  });

  it("uses the featured position and saved player in the player-facing pick confirmation", () => {
    expect(positionLabel("RB")).toBe("running back");
    expect(positionLabel("TE")).toBe("tight end");
    expect(pickConfirmationMessage("Ahmad Hardy")).toBe(
      "Your pick is in. Follow Ahmad Hardy this Saturday.",
    );
    expect(
      lockDeadlineMessage("Ahmad Hardy", "2026-09-05T16:00:00Z"),
    ).toContain("Ahmad Hardy's game starts at");
    expect(
      lockDeadlineMessage("Ahmad Hardy", "2026-09-05T16:00:00Z"),
    ).toContain("Pick before kickoff; then it will lock.");
  });

  it("reveals a sponsor reward only for a finalized winning entry", () => {
    expect(shouldRevealSponsorReward("OPEN", { is_winner: true })).toBe(false);
    expect(shouldRevealSponsorReward("FINAL", { is_winner: false })).toBe(
      false,
    );
    expect(shouldRevealSponsorReward("FINAL", null)).toBe(false);
    expect(shouldRevealSponsorReward("FINAL", { is_winner: true })).toBe(true);
  });

  it("keeps disabled and empty contests in coming soon but previews a valid scheduled slate", () => {
    expect(isSaturdayPick6ComingSoon(undefined)).toBe(true);
    expect(isSaturdayPick6ComingSoon({ status: "OPEN", players: [] })).toBe(
      true,
    );
    expect(
      isSaturdayPick6ComingSoon({ status: "SCHEDULED", players: [player] }),
    ).toBe(false);
    expect(
      isSaturdayPick6ComingSoon({ status: "OPEN", players: [player] }),
    ).toBe(false);
    expect(SATURDAY_PICK_6_COMING_SOON_MESSAGE).toBe(
      "Week 1 picks are coming soon. Six featured players will be available once weekly projections are published.",
    );
  });

  it("does not treat a public sponsor brand as a reward source", () => {
    const sponsor = { name: "Example Sponsor", logo_url: null };
    expect(getSaturdayPickSponsorLogo(sponsor)).toBeNull();
    expect(getSaturdayPickRewardMessage(sponsor)).toContain("final scoring");
  });
});
