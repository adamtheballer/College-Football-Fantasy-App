import { describe, expect, it } from "vitest";
import fixture from "../../../shared/challenge-experiences.fixture.json";
import { experienceEntryError } from "./ExperienceEntry";
import type { Challenge, Pick } from "@/hooks/use-weekly-challenges";
const get = (kind: string) =>
  structuredClone(fixture.challenges.find((c) => c.kind === kind)) as Challenge;
const lineup: Pick[] = [
  { player_id: 101, slot: "QB" },
  { player_id: 102, slot: "RB" },
  { player_id: 103, slot: "WR1" },
  { player_id: 107, slot: "WR2" },
  { player_id: 104, slot: "TE" },
  { player_id: 105, slot: "FLEX" },
];
describe("expanded challenge entry preflight", () => {
  it("accepts a six-player formation with two distinct receivers and a valid FLEX", () => {
    expect(experienceEntryError(get("millionaire"), lineup, true)).toBeNull();
  });
  it("rejects a duplicate player across two slots", () => {
    const picks = lineup.map((p) => ({ ...p }));
    picks[5].player_id = 102;
    expect(experienceEntryError(get("millionaire"), picks, true)).toMatch(
      /unique/,
    );
  });
  it("rejects over-budget, unpriced and mispositioned players", () => {
    let c = get("millionaire");
    c.experience!.salaries[0].salary = 60;
    expect(experienceEntryError(c, lineup, true)).toMatch(/exceeds/);
    c = get("millionaire");
    c.experience!.salaries = [];
    expect(experienceEntryError(c, lineup, true)).toMatch(/eligible/);
    const picks = lineup.map((p) => ({ ...p }));
    picks[0].player_id = 106;
    picks[1].slot = "TE";
    expect(
      experienceEntryError(get("millionaire"), picks, true),
    ).not.toBeNull();
  });
  it("allows partial drafts but blocks incomplete submissions", () => {
    expect(
      experienceEntryError(get("millionaire"), lineup.slice(0, 2), false),
    ).toBeNull();
    expect(
      experienceEntryError(get("millionaire"), lineup.slice(0, 2), true),
    ).toMatch(/six/);
  });
  it("requires school allegiance and one side per Fan Wars game", () => {
    const c = get("fanwars");
    const choices = [{ game_id: 1, team: "Alabama" }];
    expect(experienceEntryError(c, choices, true)).toMatch(/school/);
    c.experience!.allegiance = { id: 1, name: "Alabama", conference: "SEC" };
    expect(experienceEntryError(c, choices, true)).toBeNull();
    expect(experienceEntryError(c, [...choices, ...choices], true)).toMatch(
      /one side/,
    );
  });
  it("requires all ten creator games", () => {
    const c = get("creator");
    const choices = c.games.map((g) => ({ game_id: g.id, team: g.home_team }));
    expect(experienceEntryError(c, choices, true)).toBeNull();
    expect(experienceEntryError(c, choices.slice(0, 9), true)).toMatch(/10/);
  });
  it("blocks survivor team reuse in the same series", () => {
    const c = get("survivor");
    c.experience!.previous_picks = [
      {
        week: 7,
        team: "Alabama",
        opponent: "QA",
        outcome: "survived",
        game: null,
      },
    ];
    expect(
      experienceEntryError(c, [{ game_id: 1, team: "Alabama" }], true),
    ).toMatch(/already used/);
  });
});

it("rejects a player whose canonical eligibility changed after publication", () => {
  const c = get("millionaire");
  c.experience!.ineligible_player_ids = [101];
  expect(experienceEntryError(c, lineup, true)).toMatch(/eligible/);
});
