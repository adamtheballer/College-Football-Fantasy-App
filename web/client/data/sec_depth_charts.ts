export type DepthPlayer = {
  depth: number;
  name: string;
  classYear: string;
  firstYearStarter?: boolean;
};

export type TeamDepthChart = {
  team: string;
  conference: "SEC";
  positions: {
    QB: DepthPlayer[];
    RB: DepthPlayer[];
    WR: DepthPlayer[];
    TE: DepthPlayer[];
    K: DepthPlayer[];
  };
};

const NOT_SURE: DepthPlayer = { depth: 0, name: "not sure", classYear: "not sure" };

export const secDepthCharts: TeamDepthChart[] = [
  {
    team: "Alabama",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Austin Mack", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Keelon Russell", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Daniel Hill", classYear: "Sophomore" },
        { depth: 2, name: "AK Dear", classYear: "Freshman" },
        { depth: 3, name: "Kevin Riley", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Noah Rogers", classYear: "Junior" },
        { depth: 2, name: "Ryan Williams", classYear: "Junior" },
        { depth: 3, name: "Lotzeir Brooks", classYear: "Sophomore" },
        { depth: 4, name: "Derek Meadows", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Kaleb Edwards", classYear: "Sophomore" },
        { depth: 2, name: "Danny Lewis Jr.", classYear: "Senior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Arkansas",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "KJ Jackson", classYear: "Sophomore", firstYearStarter: true },
        { depth: 2, name: "AJ Hill", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Braylen Russell", classYear: "Junior" },
        { depth: 2, name: "Jasper Parker", classYear: "Sophomore" },
        { depth: 3, name: "Sutton Smith", classYear: "Senior" },
      ],
      WR: [
        { depth: 1, name: "Donovan Faupel", classYear: "Senior" },
        { depth: 2, name: "Chris Marshall", classYear: "Senior" },
        { depth: 3, name: "Jamari Hawkins", classYear: "Senior" },
        { depth: 4, name: "Jelani Watkins", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Jaden Platt", classYear: "Junior" },
        { depth: 2, name: "Ty Lockwood", classYear: "Senior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Auburn",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Byrum Brown", classYear: "Senior", firstYearStarter: true },
        { depth: 2, name: "Tristan Ti'a", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Jeremiah Cobb", classYear: "Senior" },
        { depth: 2, name: "Bryson Washington", classYear: "Junior" },
        { depth: 3, name: "Nykahi Davenport", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Chas Nimrod", classYear: "Senior" },
        { depth: 2, name: "Keshaun Singleton", classYear: "Junior" },
        { depth: 3, name: "Bryce Cain", classYear: "Sophomore" },
        { depth: 4, name: "Jeremiah Koger", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Jake Johnson", classYear: "Senior", firstYearStarter: true },
        { depth: 2, name: "Jonathan Echols", classYear: "Sophomore" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Florida",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Aaron Philo", classYear: "Sophomore", firstYearStarter: true },
        { depth: 2, name: "Tramell Jones Jr.", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Jadan Baugh", classYear: "Junior" },
        { depth: 2, name: "Evan Pryor", classYear: "Senior" },
        { depth: 3, name: "London Montgomery", classYear: "Junior" },
      ],
      WR: [
        { depth: 1, name: "Dallas Wilson", classYear: "Freshman" },
        { depth: 2, name: "Eric Singleton Jr.", classYear: "Senior" },
        { depth: 3, name: "Vernell Brown III", classYear: "Sophomore" },
        { depth: 4, name: "Micah Mays Jr.", classYear: "Junior", firstYearStarter: true },
      ],
      TE: [
        { depth: 1, name: "Luke Harpring", classYear: "Sophomore" },
        { depth: 2, name: "Amir Jackson", classYear: "Sophomore" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Georgia",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Gunner Stockton", classYear: "Senior" },
        { depth: 2, name: "Ryan Puglisi", classYear: "Sophomore" },
      ],
      RB: [
        { depth: 1, name: "Nate Frazier", classYear: "Junior" },
        { depth: 2, name: "Chauncey Bowens", classYear: "Sophomore" },
        { depth: 3, name: "Dante Dowdell", classYear: "Senior" },
      ],
      WR: [
        { depth: 1, name: "Isiah Canion", classYear: "Junior" },
        { depth: 2, name: "London Humphreys", classYear: "Senior" },
        { depth: 3, name: "Sacovie White-Helton", classYear: "Sophomore" },
        { depth: 4, name: "CJ Wiley", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Lawson Luckie", classYear: "Senior" },
        { depth: 2, name: "Elyiss Williams", classYear: "Sophomore" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Kentucky",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Kenny Minchey", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Matt Ponatoski", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "CJ Baxter", classYear: "Junior" },
        { depth: 2, name: "Jovantae Barnes", classYear: "Senior" },
        { depth: 3, name: "Jason Patterson", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "DJ Miller", classYear: "Sophomore" },
        { depth: 2, name: "Nic Anderson", classYear: "Senior", firstYearStarter: true },
        { depth: 3, name: "Kenny Darby", classYear: "Freshman" },
        { depth: 4, name: "Shane Carr", classYear: "Junior" },
      ],
      TE: [
        { depth: 1, name: "Henry Boyer", classYear: "Senior" },
        { depth: 2, name: "Willie Rodriguez", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "LSU",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Sam Leavitt", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Husan Longstreet", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Harlem Berry", classYear: "Sophomore" },
        { depth: 2, name: "Caden Durham", classYear: "Junior" },
        { depth: 3, name: "Dilin Jones", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Eugene Wilson III", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Jayce Brown", classYear: "Senior", firstYearStarter: true },
        { depth: 3, name: "Winston Watkins", classYear: "Sophomore", firstYearStarter: true },
        { depth: 4, name: "Jackson Harris", classYear: "Junior" },
      ],
      TE: [
        { depth: 1, name: "Trey'Dez Green", classYear: "Junior" },
        { depth: 2, name: "Zach Grace", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Mississippi State",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Kamario Taylor", classYear: "Sophomore", firstYearStarter: true },
        { depth: 2, name: "AJ Swann", classYear: "Senior" },
      ],
      RB: [
        { depth: 1, name: "Fluff Bothwell", classYear: "Junior" },
        { depth: 2, name: "Xavier Gayten", classYear: "Junior" },
        { depth: 3, name: "Kolin Wilson", classYear: "Freshman" },
      ],
      WR: [
        { depth: 1, name: "Marquis Johnson", classYear: "Senior" },
        { depth: 2, name: "Ayden Williams", classYear: "Senior" },
        { depth: 3, name: "Anthony Evans III", classYear: "Senior" },
        { depth: 4, name: "Sanfrisco Magee", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Sam West", classYear: "Junior" },
        { depth: 2, name: "Riley Williams", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Missouri",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Austin Simmons", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Nick Evers", classYear: "Senior" },
      ],
      RB: [
        { depth: 1, name: "Ahmad Hardy", classYear: "Junior" },
        { depth: 2, name: "Jamal Roberts", classYear: "Junior" },
        { depth: 3, name: "Xai'Shaun Edwards", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Donovan Olugbode", classYear: "Sophomore" },
        { depth: 2, name: "Caleb Goodie", classYear: "Senior" },
        { depth: 3, name: "Cayden Lee", classYear: "Senior" },
        { depth: 4, name: "Kenric Lanier II", classYear: "Junior" },
      ],
      TE: [
        { depth: 1, name: "Brett Norfleet", classYear: "Senior" },
        { depth: 2, name: "Jordon Harris", classYear: "Senior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Oklahoma",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "John Mateer", classYear: "Senior" },
        { depth: 2, name: "Whitt Newbauer", classYear: "Junior" },
      ],
      RB: [
        { depth: 1, name: "Xavier Robinson", classYear: "Junior" },
        { depth: 2, name: "Tory Blaylock", classYear: "Sophomore" },
        { depth: 3, name: "Lloyd Avant", classYear: "Junior" },
      ],
      WR: [
        { depth: 1, name: "Trell Harris", classYear: "Senior" },
        { depth: 2, name: "Parker Livingstone", classYear: "Sophomore" },
        { depth: 3, name: "Isaiah Sategna III", classYear: "Senior" },
        { depth: 4, name: "Elijah Thomas", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Hayden Hansen", classYear: "Senior" },
        { depth: 2, name: "Rocky Beers", classYear: "Senior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Ole Miss",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Trinidad Chambliss", classYear: "Senior" },
        { depth: 2, name: "Deuce Knight", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Kewan Lacy", classYear: "Junior" },
        { depth: 2, name: "Makhi Frazier", classYear: "Junior" },
        { depth: 3, name: "Joshua Dye", classYear: "Junior" },
      ],
      WR: [
        { depth: 1, name: "Deuce Alexander", classYear: "Junior" },
        { depth: 2, name: "Darrell Gill Jr.", classYear: "Senior" },
        { depth: 3, name: "Johntay Cook", classYear: "Senior" },
        { depth: 4, name: "Horatio Fields", classYear: "Senior" },
      ],
      TE: [
        { depth: 1, name: "Luke Hasz", classYear: "Senior" },
        { depth: 2, name: "Brady Prieskorn", classYear: "Sophomore" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "South Carolina",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "LaNorris Sellers", classYear: "Junior" },
        { depth: 2, name: "Cutter Woods", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Matt Fuller", classYear: "Sophomore" },
        { depth: 2, name: "Jawarn Howell", classYear: "Junior" },
        { depth: 3, name: "Christian Clark", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Nitro Tuggle", classYear: "Junior" },
        { depth: 2, name: "Nyck Harbor", classYear: "Senior" },
        { depth: 3, name: "Jayden Sellers", classYear: "Sophomore" },
        { depth: 4, name: "Jayden Gibson", classYear: "Senior" },
      ],
      TE: [
        { depth: 1, name: "Brady Hunt", classYear: "Graduate" },
        { depth: 2, name: "Max Drag", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Tennessee",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "George MacIntyre", classYear: "Freshman", firstYearStarter: true },
        { depth: 2, name: "Faizon Brandon", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "DeSean Bishop", classYear: "Junior" },
        { depth: 2, name: "Daune Morris", classYear: "Sophomore" },
        { depth: 3, name: "Jayvin Gordon", classYear: "Sophomore" },
      ],
      WR: [
        { depth: 1, name: "Mike Matthews", classYear: "Junior" },
        { depth: 2, name: "Radarius Jackson", classYear: "Sophomore" },
        { depth: 3, name: "Braylon Staley", classYear: "Sophomore" },
        { depth: 4, name: "Travis Smith Jr.", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Ethan Davis", classYear: "Junior" },
        { depth: 2, name: "DaSaahn Brame", classYear: "Sophomore" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Texas A&M",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Marcel Reed", classYear: "Junior" },
        { depth: 2, name: "Brady Hart", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Rueben Owens II", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Jamarion Morrow", classYear: "Sophomore" },
        { depth: 3, name: "KJ Edwards", classYear: "Freshman" },
      ],
      WR: [
        { depth: 1, name: "Isaiah Horton", classYear: "Senior" },
        { depth: 2, name: "Ashton Bethel-Roman", classYear: "Sophomore" },
        { depth: 3, name: "Mario Craver", classYear: "Junior" },
        { depth: 4, name: "TK Norman", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Houston Thomas", classYear: "Senior", firstYearStarter: true },
        { depth: 2, name: "Richie Anderson III", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Texas",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Arch Manning", classYear: "Junior" },
        { depth: 2, name: "Karle Lacey Jr.", classYear: "Freshman" },
      ],
      RB: [
        { depth: 1, name: "Hollywood Smothers", classYear: "Junior" },
        { depth: 2, name: "Raleek Brown", classYear: "Senior" },
        { depth: 3, name: "James Simon", classYear: "Freshman" },
      ],
      WR: [
        { depth: 1, name: "Cam Coleman", classYear: "Junior", firstYearStarter: true },
        { depth: 2, name: "Ryan Wingo", classYear: "Junior" },
        { depth: 3, name: "Emmett Mosley V", classYear: "Junior" },
        { depth: 4, name: "Sterling Berkhalter", classYear: "Senior" },
      ],
      TE: [
        { depth: 1, name: "Nick Townsend", classYear: "Sophomore" },
        { depth: 2, name: "Michael Masunas", classYear: "Senior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
  {
    team: "Vanderbilt",
    conference: "SEC",
    positions: {
      QB: [
        { depth: 1, name: "Jared Curtis", classYear: "Freshman", firstYearStarter: true },
        { depth: 2, name: "Blaze Berlowitz", classYear: "Junior" },
      ],
      RB: [
        { depth: 1, name: "Sedrick Alexander", classYear: "Senior" },
        { depth: 2, name: "Makhilyn Young", classYear: "Junior" },
        { depth: 3, name: "Evan Hampton", classYear: "Freshman" },
      ],
      WR: [
        { depth: 1, name: "Ja'Cory Thomas", classYear: "Senior" },
        { depth: 2, name: "Junior Sherrill", classYear: "Senior" },
        { depth: 3, name: "Cole Adams", classYear: "Junior" },
        { depth: 4, name: "Brycen Coleman", classYear: "Sophomore" },
      ],
      TE: [
        { depth: 1, name: "Cole Spence", classYear: "Senior" },
        { depth: 2, name: "Jayvontay Conner", classYear: "Junior" },
      ],
      K: [
        { ...NOT_SURE, depth: 1 },
        { ...NOT_SURE, depth: 2 },
      ],
    },
  },
];
