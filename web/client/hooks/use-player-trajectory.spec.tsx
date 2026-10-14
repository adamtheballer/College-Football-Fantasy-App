// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {act,cleanup,renderHook,waitFor} from "@testing-library/react";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {usePlayerTrajectory} from "./use-players";
const {get}=vi.hoisted(()=>({get:vi.fn()}));
vi.mock("@/lib/api",()=>({apiGet:get,getLeaguePlayerHistory:vi.fn()}));
vi.mock("./use-injury-updates",()=>({useInjuryUpdates:()=>({data:{data:[]}})}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const wrapper=()=>{const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});return({children}:{children:React.ReactNode})=><QueryClientProvider client={client}>{children}</QueryClientProvider>;};
const response=(id:number,season=2026,league_id:number|null=null)=>({player_id:id,season,league_id,projection:[],value:[]});
describe("Player trajectory request ownership",()=>{
  it.each([undefined,false])("rejects live or unproven actual totals (%s)",async is_finalized=>{
    get.mockResolvedValue({...response(1),projection:[{week:1,points:20,actual_points:18.4,source:"published",is_finalized}]});
    const {result}=renderHook(()=>usePlayerTrajectory(1,2026),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isError).toBe(true));expect(String(result.current.error)).toContain("weekly finality");
  });
  it.each([response(2),response(1,2025),response(1,2026,7)])("rejects a mismatched context %#",async payload=>{
    get.mockResolvedValue(payload);
    const {result}=renderHook(()=>usePlayerTrajectory(1,2026),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isError).toBe(true));
    expect(String(result.current.error)).toContain("does not match");expect(result.current.data).toBeUndefined();
  });
  it("aborts old player/season/league requests and ignores a late response",async()=>{
    let finish:()=>void=()=>{};let oldSignal:AbortSignal|undefined;
    get.mockImplementation(async(path:string,params:{season:number;league_id?:number},signal:AbortSignal)=>{
      if(path==="/players/1/trajectory") {oldSignal=signal;await new Promise<void>(resolve=>{finish=resolve;});return response(1,params.season,params.league_id??null);}
      return response(2,params.season,params.league_id??null);
    });
    const {result,rerender}=renderHook(({id,season,league})=>usePlayerTrajectory(id,season,league),{initialProps:{id:1,season:2025,league:7},wrapper:wrapper()});
    await waitFor(()=>expect(oldSignal).toBeDefined());rerender({id:2,season:2026,league:8});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));expect(oldSignal?.aborted).toBe(true);
    await act(async()=>{finish();});expect(result.current.data).toMatchObject({player_id:2,season:2026,league_id:8});
  });
  it("retains the last valid series when background refresh fails",async()=>{
    get.mockResolvedValue(response(1));const {result}=renderHook(()=>usePlayerTrajectory(1,2026),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));get.mockRejectedValue(new Error("offline"));
    await act(async()=>{await result.current.refetch();});
    await waitFor(()=>expect(result.current.isError).toBe(true));expect(result.current.data?.player_id).toBe(1);
  });
});
