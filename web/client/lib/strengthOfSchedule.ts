import { getMatchupGrade, matchupGradeColor } from "@/lib/matchupGrades";

const OPPONENT_POOL = [
  "Alabama",
  "Georgia",
  "Texas",
  "LSU",
  "Oklahoma",
  "Florida",
  "Tennessee",
  "Ohio State",
  "Michigan",
  "Oregon",
  "Penn State",
  "USC",
  "Texas A&M",
  "Ole Miss",
  "Auburn",
  "Arkansas",
  "Notre Dame",
  "Florida State",
  "Clemson",
  "Miami",
  "Kansas State",
  "Utah",
  "TCU",
  "Baylor",
];

const hashString = (value: string) => {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) % 100000;
  }
  return hash;
};

export type SchedulePreview = {
  opponent: string;
  grade: string;
  colorClass: string;
};

export const getSchedulePreview = (team: string, pos: string, weeks = 4): SchedulePreview[] => {
  const seed = hashString(`${team}-${pos}`);
  const picks: SchedulePreview[] = [];
  for (let i = 0; i < weeks; i += 1) {
    const opponent = OPPONENT_POOL[(seed + i * 7) % OPPONENT_POOL.length];
    const matchup = getMatchupGrade(opponent, pos);
    picks.push({
      opponent,
      grade: matchup.grade,
      colorClass: matchupGradeColor(matchup.grade),
    });
  }
  return picks;
};
