export type MatchupGrade = {
  grade: "A+" | "A" | "B" | "C" | "D" | "F";
  rank: number;
  yardsPerTarget: number;
  yardsPerRush: number;
  pressureRate: number;
};

const hashString = (value: string) => {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) % 100000;
  }
  return hash;
};

const gradeFromRank = (rank: number) => {
  if (rank >= 101) return "A+";
  if (rank >= 86) return "A";
  if (rank >= 66) return "B";
  if (rank >= 46) return "C";
  if (rank >= 26) return "D";
  return "F";
};

export const getMatchupGrade = (team: string, pos: string): MatchupGrade => {
  const seed = hashString(`${team}-${pos}`);
  const rank = (seed % 130) + 1;
  const grade = gradeFromRank(rank);
  const yardsPerTarget = Number((6 + (seed % 40) / 10).toFixed(1));
  const yardsPerRush = Number((3.2 + (seed % 25) / 10).toFixed(1));
  const pressureRate = Number((0.18 + (seed % 20) / 100).toFixed(2));
  return { grade, rank, yardsPerTarget, yardsPerRush, pressureRate };
};

export const matchupGradeColor = (grade: MatchupGrade["grade"]) => {
  if (grade === "A+" || grade === "A") return "text-emerald-400";
  if (grade === "B") return "text-lime-300";
  if (grade === "C") return "text-amber-300";
  if (grade === "D") return "text-orange-400";
  return "text-red-400";
};
