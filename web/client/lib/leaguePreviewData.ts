import type {
  LeagueDetail,
  LeagueMatchupTabResponse,
  LeagueMatchupTeam,
  LeagueRosterPlayer,
  LeagueRosterTabResponse,
  LeagueSettingsTabResponse,
  LeagueWaiverTabResponse,
} from "@/types/league";

export const DEMO_LEAGUE_ID = -9001;
export const DEMO_WEEK = 1;

const nowIso = new Date().toISOString();

const demoManagers = [
  "Adam's Team",
  "Bot Manager 1",
  "Bot Manager 2",
  "Bot Manager 3",
  "Bot Manager 4",
  "Bot Manager 5",
  "Bot Manager 6",
  "Bot Manager 7",
  "Bot Manager 8",
  "Bot Manager 9",
];

const demoSlots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "BENCH", "BENCH", "BENCH", "BENCH", "IR"];

const demoPlayerNames = [
  ["Lanorris Sellers", "Ahmad Hardy", "Cam Cook", "Jeremiah Smith", "Ryan Williams", "Brett Norfleet", "LJ Martin", "Dylan Sampson", "George MacIntyre", "Jordyn Tyson", "Nick Townsend", "Ethan Davis", "Depth IR"],
  ["Cade Klubnik", "Justice Haynes", "Nate Frazier", "Carnell Tate", "Makhi Hughes", "Jake Briningstool", "Hollywood Smothers", "Jackson Harris", "John Mateer", "Donovan Green", "Lawson Luckie", "Kewan Lacy", "IR Reserve"],
  ["Garrett Nussmeier", "Bryant Wesco Jr.", "Kamarion Taylor", "Antonio Williams", "Isaac Brown", "Oscar Delp", "Sedrick Alexander", "Ashton Bethel-Roman", "Marcel Reed", "Hayden Hansen", "Jamarrion Morrow", "Ayden Greene", "IR Reserve"],
  ["Nico Iamaleava", "Le'Veon Moss", "Jaydn Ott", "Barion Brown", "Kevin Concepcion", "Mason Taylor", "Duce Robinson", "Peyton Woodring", "Trinidad Chambliss", "Arch Manning", "Byrum Brown", "Noah Thomas", "IR Reserve"],
  ["Drew Allar", "Quinshon Judkins", "Ollie Gordon II", "Tetairoa McMillan", "Evan Stewart", "Colston Loveland", "Tre Harris", "Mitch Jeter", "Miller Moss", "CJ Baxter", "Emeka Egbuka", "Oronde Gadsden", "IR Reserve"],
  ["Jaxson Dart", "TreVeyon Henderson", "Nicholas Singleton", "Luther Burden III", "Zachariah Branch", "Harold Fannin Jr.", "Jayden Higgins", "Will Stone", "Dillon Gabriel", "Makhi Hughes", "Tez Johnson", "Luke Lachey", "IR Reserve"],
  ["Riley Leonard", "Kaleb Johnson", "RJ Harvey", "Xavier Restrepo", "Elic Ayomanor", "Tyler Warren", "Omarion Hampton", "Ryan Fitzgerald", "Jalon Daniels", "Darius Taylor", "Jalen Royals", "Jack Velling", "IR Reserve"],
  ["Jalen Milroe", "Ashton Jeanty", "Tahj Brooks", "Malachi Fields", "Ricky White", "Gunnar Helm", "Devin Neal", "Andres Borregales", "Will Howard", "Raheim Sanders", "Jaylin Noel", "Moliki Matavao", "IR Reserve"],
  ["Carson Beck", "Jordan James", "Brashard Smith", "Tai Felton", "Xavier Worthy", "Bryson Nesbit", "DJ Giddens", "Cam Little", "Kurtis Rourke", "Damien Martinez", "Elijah Sarratt", "Luke Hasz", "IR Reserve"],
  ["Shedeur Sanders", "Jonah Coleman", "Kyle Monangai", "Ja'Corey Brooks", "Isaiah Bond", "Oronde Gadsden II", "Kaleb Johnson", "Caden Davis", "Brady Cook", "Devin Mockobee", "Tory Horton", "Terrance Ferguson", "IR Reserve"],
];

const schoolByPosition: Record<string, string[]> = {
  QB: ["South Carolina", "Clemson", "LSU", "UCLA", "Penn State", "Ole Miss", "Notre Dame", "Alabama", "Miami", "Colorado"],
  RB: ["Missouri", "Georgia", "Ohio State", "Oklahoma State", "Iowa", "Tennessee", "Texas", "Boise State", "Oregon", "Rutgers"],
  WR: ["Ohio State", "Alabama", "Missouri", "Arizona", "Miami", "Texas", "Stanford", "Virginia Tech", "Maryland", "TCU"],
  TE: ["Missouri", "Clemson", "Oklahoma State", "Georgia", "Michigan", "Bowling Green", "Penn State", "Texas", "North Carolina", "Syracuse"],
  K: ["Georgia", "LSU", "Texas A&M", "Florida State", "Alabama", "Texas", "Florida", "Miami", "Arkansas", "Colorado"],
};

export const DEMO_LEAGUE_DETAIL: LeagueDetail = {
  id: DEMO_LEAGUE_ID,
  name: "Alpha Demo League",
  commissioner_user_id: 1,
  season_year: 2026,
  max_teams: 10,
  is_private: true,
  invite_code: "DEMOLEAGUE",
  description: "Dev-only 10-manager demo league for roster, matchup, Available Players, and settings visuals.",
  icon_url: null,
  status: "post_draft",
  created_at: nowIso,
  updated_at: nowIso,
  settings: {
    id: DEMO_LEAGUE_ID,
    league_id: DEMO_LEAGUE_ID,
    scoring_json: {
      ppr: 1,
      pass_td: 4,
      pass_yds_per_pt: 25,
      rush_yds_per_pt: 10,
      rec_yds_per_pt: 10,
      rush_td: 6,
      rec_td: 6,
      int: -2,
      fumble_lost: -2,
      fg: 3,
      xp: 1,
    },
    roster_slots_json: {
      QB: 1,
      RB: 2,
      WR: 2,
      TE: 1,
      FLEX: 1,
      K: 1,
      BENCH: 4,
      IR: 1,
    },
    playoff_teams: 4,
    waiver_type: "faab",
    trade_review_type: "commissioner",
    superflex_enabled: false,
    kicker_enabled: true,
    defense_enabled: false,
  },
  draft: {
    id: DEMO_LEAGUE_ID,
    league_id: DEMO_LEAGUE_ID,
    draft_datetime_utc: nowIso,
    timezone: "America/New_York",
    draft_type: "snake",
    pick_timer_seconds: 90,
    status: "completed",
  },
  members: demoManagers.map((_, index) => ({
    id: DEMO_LEAGUE_ID - index,
    user_id: index + 1,
    role: index === 0 ? "commissioner" : "member",
    joined_at: nowIso,
  })),
};

const projectionForSlot = (slot: string, teamIndex: number) => {
  const baseBySlot: Record<string, number> = {
    QB: 24.8,
    RB: 15.8,
    WR: 14.9,
    TE: 10.6,
    FLEX: 13.4,
    K: 8.1,
    BENCH: 7.4,
    IR: 0,
  };
  const variance = ((teamIndex % 4) - 1.5) * 0.9;
  return Number(Math.max(0, (baseBySlot[slot] ?? 7) + variance).toFixed(1));
};

function demoPlayer({
  id,
  teamId,
  teamName,
  slot,
  index,
  name,
}: {
  id: number;
  teamId: number;
  teamName: string;
  slot: string;
  index: number;
  name: string;
}): LeagueRosterPlayer {
  const position = slot === "FLEX" ? (index % 2 === 0 ? "RB" : "WR") : slot === "BENCH" ? ["QB", "RB", "WR", "TE"][index % 4] : slot;
  const projection = projectionForSlot(slot, index);

  return {
    id,
    league_id: DEMO_LEAGUE_ID,
    team_id: teamId,
    fantasy_team_id: teamId,
    fantasy_team_name: teamName,
    player_id: id,
    player_name: name,
    player_school: schoolByPosition[position]?.[index % 10] ?? "College",
    player_position: position,
    school: schoolByPosition[position]?.[index % 10] ?? "College",
    position,
    slot,
    roster_slot: slot,
    status: "ACTIVE",
    acquisition_type: "DRAFT",
    draft_pick_id: Math.abs(id),
    is_starter: slot !== "BENCH" && slot !== "IR",
    is_ir: slot === "IR",
    opponent: ["vs TEX", "@ LSU", "vs MIA", "@ UGA", "vs ALA"][index % 5],
    projected_points: projection,
    floor: Math.max(0, projection - 4.5),
    ceiling: projection + 7.5,
    boom_prob: 0.22 + (index % 3) * 0.03,
    bust_prob: 0.14 + (index % 4) * 0.02,
    weekly_projected_fantasy_points: projection,
  };
}

export function createDemoLeagueRosters(): LeagueRosterPlayer[] {
  return demoManagers.flatMap((teamName, teamIndex) => {
    const teamId = DEMO_LEAGUE_ID - 100 - teamIndex;
    return demoSlots.map((slot, slotIndex) =>
      demoPlayer({
        id: DEMO_LEAGUE_ID - 1000 - teamIndex * 100 - slotIndex,
        teamId,
        teamName,
        slot,
        index: teamIndex + slotIndex,
        name: demoPlayerNames[teamIndex][slotIndex],
      })
    );
  });
}

export function getDemoTeamRoster(teamIndex = 0): LeagueRosterPlayer[] {
  const teamId = DEMO_LEAGUE_ID - 100 - teamIndex;
  return createDemoLeagueRosters().filter((player) => player.fantasy_team_id === teamId);
}

const startersTotal = (roster: LeagueRosterPlayer[]) =>
  roster
    .filter((player) => player.is_starter)
    .reduce((total, player) => total + Number(player.weekly_projected_fantasy_points ?? 0), 0);

export function createDemoLeagueRosterResponse(): LeagueRosterTabResponse {
  const roster = getDemoTeamRoster(0);
  return {
    league_id: DEMO_LEAGUE_ID,
    season: 2026,
    fantasy_team_id: DEMO_LEAGUE_ID - 100,
    fantasy_team_name: "Adam's Team",
    owned_team: {
      id: DEMO_LEAGUE_ID - 100,
      league_id: DEMO_LEAGUE_ID,
      name: "Adam's Team",
      owner_user_id: 1,
    },
    week: DEMO_WEEK,
    roster,
    data: roster,
    roster_slot_limits: DEMO_LEAGUE_DETAIL.settings.roster_slots_json,
    ir_slots: 1,
    message: "Dev-only 10-team placeholder roster.",
  };
}

export function createDemoLeagueMatchupResponse(): LeagueMatchupTabResponse {
  const myRoster = getDemoTeamRoster(0);
  const opponentRoster = getDemoTeamRoster(1);
  const myTotal = startersTotal(myRoster);
  const opponentTotal = startersTotal(opponentRoster);
  const myWinProbability = Math.round((myTotal / (myTotal + opponentTotal)) * 100);

  return {
    league_id: DEMO_LEAGUE_ID,
    season: 2026,
    matchup_id: DEMO_LEAGUE_ID - 500,
    week: DEMO_WEEK,
    status: "projected",
    user_team: {
      fantasy_team_id: DEMO_LEAGUE_ID - 100,
      fantasy_team_name: "Adam's Team",
      record: "0-0",
      projected_total: myTotal,
      projected_points: myTotal,
      win_probability: myWinProbability,
      roster: myRoster,
    },
    my_team: {
      fantasy_team_id: DEMO_LEAGUE_ID - 100,
      fantasy_team_name: "Adam's Team",
      record: "0-0",
      projected_total: myTotal,
      projected_points: myTotal,
      win_probability: myWinProbability,
      roster: myRoster,
    },
    opponent_team: {
      fantasy_team_id: DEMO_LEAGUE_ID - 101,
      fantasy_team_name: "Bot Manager 1",
      record: "0-0",
      projected_total: opponentTotal,
      projected_points: opponentTotal,
      win_probability: 100 - myWinProbability,
      roster: opponentRoster,
    },
    my_roster: myRoster,
    opponent_roster: opponentRoster,
    projection_source: "dev-demo",
    message: "Projected Week 1 matchup from generated demo rosters.",
  };
}

const demoWaiverCandidateRows = [
  "Dylan Raiola|Nebraska|QB|15.2",
  "LaNorris Sellers|South Carolina|QB|14.8",
  "Haynes King|Georgia Tech|QB|13.7",
  "Avery Johnson|Kansas State|QB|12.9",
  "Maalik Murphy|Oregon State|QB|12.4",
  "Dylan Lonergan|Boston College|QB|11.8",
  "Taylen Green|Arkansas|QB|11.1",
  "Brock Glenn|Florida State|QB|10.7",
  "Malachi Toney|Miami|WR|12.8",
  "Cam Coleman|Texas|WR|13.6",
  "Jackson Harris|LSU|WR|9.1",
  "Jordan Faison|Notre Dame|WR|10.4",
  "Ryan Wingo|Texas|WR|10.2",
  "Carnell Tate|Ohio State|WR|9.8",
  "Dakorien Moore|Oregon|WR|9.4",
  "Bryant Wesco Jr.|Clemson|WR|9.2",
  "Nate Frazier|Georgia|RB|11.9",
  "Isaac Brown|Louisville|RB|10.7",
  "Jamarrion Morrow|Texas A&M|RB|9.8",
  "Bo Jackson|Ohio State|RB|9.6",
  "Wayne Knight|UCLA|RB|9.2",
  "Jadan Baugh|Florida|RB|9.0",
  "Mark Fletcher Jr.|Miami|RB|8.8",
  "Hayden Hansen|Oklahoma|TE|9.4",
  "Jaden Platt|Arkansas|TE|8.9",
  "Lawson Luckie|Georgia|TE|8.6",
  "Nick Townsend|Texas|TE|8.3",
  "Ethan Davis|Tennessee|TE|8.1",
  "Brett Norfleet|Missouri|TE|7.9",
  "Terrance Carter Jr.|Texas Tech|TE|9.6",
  "Trey'Dez Green|LSU|TE|9.5",
  "Jamari Johnson|Oregon|TE|9.0",
  "Dorian Thomas|Cal|TE|8.7",
  "Benjamin Brahmer|Penn State|TE|8.5",
  "DJ Vonnahme|Iowa|TE|8.2",
  "Dylan Wade|UCF|TE|8.0",
  "Peter Clarke|Temple|TE|7.8",
  "Parker Lewis|Ohio State|K|7.8",
  "Tate Sandell|Oklahoma|K|7.5",
  "Peyton Woodring|Georgia|K|7.3",
  "Brock Taylor|Vanderbilt|K|7.0",
  "Lucas Carneiro|Ole Miss|K|6.8",
];

export function createDemoLeagueWaiverResponse(): LeagueWaiverTabResponse {
  const draftedPlayerNames = new Set(
    createDemoLeagueRosters().map((player) => player.player_name.toLowerCase())
  );
  const availablePlayers = demoWaiverCandidateRows
    .map((row, index) => {
      const [name, school, position, points] = row.split("|");
      return {
        id: DEMO_LEAGUE_ID - 3000 - index,
        name,
        school,
        position,
        weekly_projected_fantasy_points: Number(points),
      };
    })
    .filter((player) => !draftedPlayerNames.has(player.name.toLowerCase()))
    .sort(
      (first, second) =>
        Number(second.weekly_projected_fantasy_points ?? 0) -
        Number(first.weekly_projected_fantasy_points ?? 0) ||
        first.name.localeCompare(second.name)
    );

  return {
    league_id: DEMO_LEAGUE_ID,
    fantasy_team_id: DEMO_LEAGUE_ID - 100,
    total_available: availablePlayers.length,
    claims: [],
    available_players: availablePlayers,
  };
}

export function createDemoLeagueSettingsResponse(): LeagueSettingsTabResponse {
  const rosters = createDemoLeagueRosters();
  const schedule = Array.from({ length: 8 }, (_, weekIndex) => {
    const week = weekIndex + 1;
    const rotatedManagers = [
      demoManagers[0],
      ...demoManagers.slice(1 + weekIndex),
      ...demoManagers.slice(1, 1 + weekIndex),
    ];

    return Array.from({ length: 5 }, (_, matchupIndex) => {
      const homeIndex = matchupIndex * 2;
      const awayIndex = homeIndex + 1;
      const homeName = rotatedManagers[homeIndex];
      const awayName = rotatedManagers[awayIndex];
      const homeOriginalIndex = demoManagers.indexOf(homeName);
      const awayOriginalIndex = demoManagers.indexOf(awayName);
      const homeProjection = 112.4 - matchupIndex * 2.2 + weekIndex * 0.7;
      const awayProjection = 108.8 + matchupIndex * 1.6 - weekIndex * 0.35;
      const homeWinProbability = Math.round((homeProjection / (homeProjection + awayProjection)) * 100);

      return {
        matchup_id: DEMO_LEAGUE_ID - 600 - weekIndex * 10 - matchupIndex,
        week,
        home_team_id: DEMO_LEAGUE_ID - 100 - homeOriginalIndex,
        home_team_name: homeName,
        away_team_id: DEMO_LEAGUE_ID - 100 - awayOriginalIndex,
        away_team_name: awayName,
        home_projected_total: Number(homeProjection.toFixed(1)),
        away_projected_total: Number(awayProjection.toFixed(1)),
        home_win_probability: homeWinProbability,
        away_win_probability: 100 - homeWinProbability,
      };
    });
  }).flat();

  return {
    league_id: DEMO_LEAGUE_ID,
    league_name: DEMO_LEAGUE_DETAIL.name,
    league_info: {
      season_year: 2026,
      status: "post_draft",
      teams: 10,
      members: "10/10",
      draft_status: "completed",
    },
    members: DEMO_LEAGUE_DETAIL.members,
    scoring_settings: DEMO_LEAGUE_DETAIL.settings.scoring_json,
    roster_settings: DEMO_LEAGUE_DETAIL.settings.roster_slots_json,
    waiver_rules: {
      waiver_type: "FAAB",
      budget: 100,
      league_scoped: true,
    },
    standings: demoManagers.map((name, index) => ({
      team_id: DEMO_LEAGUE_ID - 100 - index,
      team_name: name,
      record: "0-0",
      points_for: 0,
      rank: index + 1,
    })),
    schedule,
    rosters,
    draft_results: rosters
      .filter((player) => player.roster_slot !== "IR")
      .slice(0, 60)
      .map((player, index) => ({
        draft_pick_id: player.draft_pick_id ?? index + 1,
        overall_pick: index + 1,
        team_name: player.fantasy_team_name,
        player_name: player.player_name,
        position: player.position ?? player.player_position ?? null,
      })),
    commissioner_controls: ["reschedule_draft", "edit_settings", "review_trades"],
  };
}
