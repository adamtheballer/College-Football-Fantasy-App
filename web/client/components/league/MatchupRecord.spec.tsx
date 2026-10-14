// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MatchupRecord, currentRecordHighlight } from "./MatchupRecord";
import type { LeagueMatchupTabResponse } from "@/types/league";
afterEach(cleanup);
const response = (): LeagueMatchupTabResponse => ({league_id:42,season:2026,week:6,current_matchup_week:6,matchup_id:66,status:"final",matchup_week_rollover_at:"2026-10-14T04:00:00Z",user_team:{fantasy_team_id:1,fantasy_team_name:"Winner",record:"12-3-0",record_highlight:"win",roster:[],current_points:0},opponent_team:{fantasy_team_id:2,fantasy_team_name:"Loser",record:"3-12-0",record_highlight:"loss",roster:[],current_points:500}});
const now=Date.parse("2026-10-13T20:00:00Z");
describe("Matchup-only applied record highlight",()=>{
 it("colors only the complete win/loss count and preserves inline text",()=>{
  const view=render(<p className="text-cfb-text-muted"><MatchupRecord record="12-3-0" highlight="win" /></p>);
  expect(view.container.textContent).toBe("12-3-0");
  expect(view.container.querySelector('[data-record-count="wins"]')?.className).toBe("text-emerald-300");
  expect(view.container.querySelector('[data-record-count="losses"]')?.className).toBe("");
  view.rerender(<p className="text-cfb-text-muted"><MatchupRecord record="3-12-2" highlight="loss" /></p>);
  expect(view.container.textContent).toBe("3-12-2");
  expect(view.container.querySelector('[data-record-count="losses"]')?.className).toBe("text-red-400");
  expect(view.container.querySelector('[data-record-count="wins"]')?.className).toBe("");
  expect(view.container.querySelector('[data-record-count="ties"]')?.className).toBe("");
 });
 it("uses the certified outcome for both teams despite contradictory displayed scores",()=>{
  const data=response();
  expect(currentRecordHighlight(data,data.user_team,42,2026,now)).toBe("win");
  expect(currentRecordHighlight(data,data.opponent_team,42,2026,now)).toBe("loss");
 });
 it.each(["live","projected","scheduled","delayed","unavailable",null])("stays neutral before official finality (%s)",status=>{
  const data={...response(),status};expect(currentRecordHighlight(data,data.user_team,42,2026,now)).toBeNull();
 });
 it("is neutral without confirmation and keeps ties neutral",()=>{
  const data=response();data.user_team!.record_highlight=null;
  expect(currentRecordHighlight(data,data.user_team,42,2026,now)).toBeNull();
  const view=render(<MatchupRecord record="3-3-2" highlight={null}/>);
  expect(view.container.textContent).toBe("3-3-2");expect(view.container.querySelector('[class]')).toBeNull();
 });
 it("persists on ordinary rereads until the server's rollover, including its exact boundary",()=>{
  const data=response(),boundary=Date.parse(data.matchup_week_rollover_at!);
  for(const instant of [now,now+60_000,boundary-1]) expect(currentRecordHighlight({...data},data.user_team,42,2026,instant)).toBe("win");
  expect(currentRecordHighlight(data,data.user_team,42,2026,boundary)).toBeNull();
  expect(currentRecordHighlight(data,data.opponent_team,42,2026,boundary+1)).toBeNull();
 });
 it("rejects league/season leaks, historical weeks, byes and malformed boundaries",()=>{
  const data=response();
  expect(currentRecordHighlight(data,data.user_team,43,2026,now)).toBeNull();
  expect(currentRecordHighlight(data,data.user_team,42,2027,now)).toBeNull();
  expect(currentRecordHighlight({...data,current_matchup_week:7},data.user_team,42,2026,now)).toBeNull();
  expect(currentRecordHighlight({...data,matchup_id:null},data.user_team,42,2026,now)).toBeNull();
  expect(currentRecordHighlight({...data,matchup_week_rollover_at:"invalid"},data.user_team,42,2026,now)).toBeNull();
 });
 it("a correction swaps outcomes without changing or incrementing record counts",()=>{
  const data=response();data.status="stat_corrected";data.user_team!.record="11-4-0";data.user_team!.record_highlight="loss";
  const view=render(<MatchupRecord record={data.user_team!.record} highlight={currentRecordHighlight(data,data.user_team,42,2026,now)}/>);
  expect(view.container.textContent).toBe("11-4-0");expect(view.container.querySelector('.text-red-400')?.textContent).toBe("4");
 });
});

it("does not color an unavailable, malformed, or unincremented record",()=>{
 const data=response();
 for(const record of ["", "unavailable", "0-3-0", "bad-3-0"]){data.user_team!.record=record;expect(currentRecordHighlight(data,data.user_team,42,2026,now)).toBeNull();}
});
