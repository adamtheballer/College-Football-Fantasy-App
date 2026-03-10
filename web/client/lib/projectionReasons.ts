import { Player } from "@/types/player";
import { getMatchupGrade } from "@/lib/matchupGrades";

export const buildProjectionReasons = (player: Player) => {
  const reasons: string[] = [];
  const matchup = getMatchupGrade(player.school || "TEAM", player.pos);
  if (["A+", "A"].includes(matchup.grade)) {
    reasons.push(`Favorable matchup (defense rank ${matchup.rank})`);
  } else if (["D", "F"].includes(matchup.grade)) {
    reasons.push(`Difficult matchup (defense rank ${matchup.rank})`);
  } else {
    reasons.push(`Neutral matchup (defense rank ${matchup.rank})`);
  }

  const expectedPlays = player.projection?.expectedPlays ?? 0;
  if (expectedPlays >= 35) {
    reasons.push("High team play volume expected");
  } else if (expectedPlays >= 20) {
    reasons.push("Stable offensive volume expected");
  }

  if (player.posRank && player.posRank <= 6) {
    reasons.push("Locked-in starter role and high usage share");
  } else if (player.posRank && player.posRank <= 12) {
    reasons.push("Projected role security with steady usage");
  }

  if (player.status && player.status !== "HEALTHY") {
    reasons.push(`Injury status: ${player.status}`);
  }

  const unique = Array.from(new Set(reasons));
  return unique.slice(0, 3);
};
