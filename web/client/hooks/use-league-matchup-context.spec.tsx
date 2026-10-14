// @vitest-environment jsdom
import React from "react";
import {act,cleanup,renderHook,waitFor} from "@testing-library/react";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {afterEach,describe,expect,it,vi} from "vitest";
const {get}=vi.hoisted(()=>({get:vi.fn()}));
vi.mock("@/lib/api",()=>({apiGet:get,apiPost:vi.fn(),apiPatch:vi.fn(),apiDelete:vi.fn(),ApiError:class extends Error {status=500;}}));
import {useLeagueMatchupTab,matchupRefreshInterval} from "./use-leagues";
afterEach(()=>{cleanup();vi.clearAllMocks();});
const wrapper=()=>{const client=new QueryClient({defaultOptions:{queries:{retryDelay:0,gcTime:0}}});return({children}:{children:React.ReactNode})=><QueryClientProvider client={client}>{children}</QueryClientProvider>;};
const data=(id=42,week=6,matchup=66,season=2026)=>({league_id:id,week,matchup_id:matchup,season,current_matchup_week:week,status:"final",user_team:null,opponent_team:null});
describe("matchup request scope and rollover refresh",()=>{
 it("aborts the old context and ignores its late response after league/week/season switching",async()=>{
  const pending:Array<{signal:AbortSignal;resolve:(value:unknown)=>void}>=[];
  get.mockImplementation((_path:string,_params:unknown,signal:AbortSignal)=>new Promise(resolve=>pending.push({signal,resolve})));
  const view=renderHook(({id,week,mid,year})=>useLeagueMatchupTab(id,week,mid,true,year),{wrapper:wrapper(),initialProps:{id:42,week:6,mid:66,year:2026}});
  await waitFor(()=>expect(pending).toHaveLength(1));
  view.rerender({id:43,week:7,mid:77,year:2027});await waitFor(()=>expect(pending).toHaveLength(2));
  expect(pending[0].signal.aborted).toBe(true);
  await act(async()=>pending[1].resolve(data(43,7,77,2027)));
  await waitFor(()=>expect(view.result.current.data?.league_id).toBe(43));
  await act(async()=>pending[0].resolve(data()));
  expect(view.result.current.data?.league_id).toBe(43);expect(view.result.current.data?.week).toBe(7);
 });
 it.each([data(43),data(42,7),data(42,6,77),data(42,6,66,2027)])("rejects a response that mismatches the requested context",async payload=>{
  get.mockResolvedValue(payload);const {result}=renderHook(()=>useLeagueMatchupTab(42,6,66,true,2026),{wrapper:wrapper()});
  await waitFor(()=>expect(result.current.isError).toBe(true));expect(result.current.data).toBeUndefined();
 });
 it("keeps finalized pages refreshing and schedules a read at the server rollover",()=>{
  const now=Date.parse("2026-10-14T03:59:58Z"),response={...data(),matchup_week_rollover_at:"2026-10-14T04:00:00Z"};
  expect(matchupRefreshInterval(response,now)).toBe(2000);
  expect(matchupRefreshInterval(response,now+2000)).toBe(30_000);
  expect(matchupRefreshInterval({...response,status:"stat_corrected"},now-60_000)).toBe(30_000);
 });
});
