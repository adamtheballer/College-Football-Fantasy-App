export type AlertType = "INJURY" | "TOUCHDOWN" | "USAGE" | "WAIVER" | "PROJECTION";

export type AlertRow = {
  id: number;
  type: AlertType;
  title: string;
  body: string;
  timestamp: string;
};

export const alertsMock: AlertRow[] = [
  {
    id: 1,
    type: "INJURY",
    title: "⚠️ Injury Alert",
    body: "Quinn Ewers left practice with shoulder soreness.",
    timestamp: "2m ago",
  },
  {
    id: 2,
    type: "TOUCHDOWN",
    title: "🚨 Touchdown",
    body: "Ryan Wingo – 42 yard TD (+10.2 fantasy points).",
    timestamp: "18m ago",
  },
  {
    id: 3,
    type: "USAGE",
    title: "📈 Usage Spike",
    body: "CJ Baxter has 8 carries in the first quarter.",
    timestamp: "1h ago",
  },
  {
    id: 4,
    type: "WAIVER",
    title: "🔥 Waiver Breakout",
    body: "Cam Coleman projected +4.1 points after depth change.",
    timestamp: "Today, 8:10 AM",
  },
  {
    id: 5,
    type: "PROJECTION",
    title: "🔁 Projection Change",
    body: "Austin Mack projection moved +3.2 points.",
    timestamp: "Yesterday, 9:24 PM",
  },
];
