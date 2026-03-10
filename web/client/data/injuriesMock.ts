export type InjuryStatus = "OUT" | "DOUBTFUL" | "QUESTIONABLE" | "PROBABLE" | "FULL";

export type InjuryRow = {
  id: number;
  name: string;
  team: string;
  pos: string;
  status: InjuryStatus;
  injury: string;
  returnTimeline: string;
  projectionDelta: number;
  lastUpdated: string;
};

export const injuriesMock: InjuryRow[] = [
  {
    id: 1,
    name: "Quinn Ewers",
    team: "TEXAS",
    pos: "QB",
    status: "QUESTIONABLE",
    injury: "Shoulder strain",
    returnTimeline: "Day-to-day",
    projectionDelta: -4.2,
    lastUpdated: "Today, 10:14 AM",
  },
  {
    id: 2,
    name: "Ashton Jeanty",
    team: "BSU",
    pos: "RB",
    status: "PROBABLE",
    injury: "Ankle soreness",
    returnTimeline: "Likely Week 1",
    projectionDelta: -1.1,
    lastUpdated: "Today, 8:40 AM",
  },
  {
    id: 3,
    name: "Luther Burden III",
    team: "MISSOURI",
    pos: "WR",
    status: "DOUBTFUL",
    injury: "Hamstring",
    returnTimeline: "1-2 weeks",
    projectionDelta: -6.8,
    lastUpdated: "Yesterday, 6:22 PM",
  },
  {
    id: 4,
    name: "Colston Loveland",
    team: "MICHIGAN",
    pos: "TE",
    status: "OUT",
    injury: "Knee sprain",
    returnTimeline: "3-4 weeks",
    projectionDelta: -9.4,
    lastUpdated: "Yesterday, 4:05 PM",
  },
  {
    id: 5,
    name: "Dillon Gabriel",
    team: "OREGON",
    pos: "QB",
    status: "QUESTIONABLE",
    injury: "Illness",
    returnTimeline: "Day-to-day",
    projectionDelta: -2.7,
    lastUpdated: "Today, 9:02 AM",
  },
];
