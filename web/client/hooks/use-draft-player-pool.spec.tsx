// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {act,cleanup,renderHook,waitFor} from "@testing-library/react";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {useDraftPlayerPool} from "./use-players";
const {get}=vi.hoisted(()=>({get:vi.fn()}));
vi.mock("@/lib/api",()=>({apiGet:get,getLeaguePlayerHistory:vi.fn()}));
vi.mock("./use-injury-updates",()=>({useInjuryUpdates:()=>({data:{data:[]}})}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const wrapper=()=>{const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});return({children}:{children:React.ReactNode})=><QueryClientProvider client={client}>{children}</QueryClientProvider>;};
function setup(total=257,changed=false) {
  get.mockImplementation(async(path:string,params:Record<string,unknown>,signal:AbortSignal)=>{
    if(path!=="/players") return {data:[]};
    expect(signal).toBeInstanceOf(AbortSignal);
    const offset=Number(params.offset),limit=Number(params.limit);
    return {ranking_version:changed&&offset>0?"changed":"version-a",ranking_season:2026,ranking_week:7,total,limit,offset,data:Array.from({length:Math.min(limit,total-offset)},(_,i)=>({id:offset+i+1,name:`Player ${offset+i+1}`,position:"WR",school:"Texas",master_draft_rank:offset+i+1,draft_projected_points:100,draft_ranking_version:"version-a"}))};
  });
}
describe("versioned complete draft catalog loading",()=>{
  it("fetches every page with a shared version and an abortable context",async()=>{
    setup();const {result}=renderHook(()=>useDraftPlayerPool({season:2026,fetchAll:true,limit:200}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data).toHaveLength(257);
    expect(get.mock.calls.filter(call=>call[0]==="/players").map(call=>call[1].offset)).toEqual([0,100,200]);
    expect(result.current.data?.data[256].masterDraftRank).toBe(257);
  });
  it("rejects a dataset version changing between pages",async()=>{
    setup(257,true);const {result}=renderHook(()=>useDraftPlayerPool({season:2026,fetchAll:true}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();expect(String(result.current.error)).toContain("changed while loading");
  });
  it("loads supplementary projections for the authoritative week rather than Week 1",async()=>{
    setup(1);const {result}=renderHook(()=>useDraftPlayerPool({season:2026}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));
    expect(get.mock.calls.find(call=>call[0]==="/projections")?.[1]).toMatchObject({season:2026,week:7});
  });
  it("rejects duplicate IDs across otherwise matching pages",async()=>{
    setup(257);const original=get.getMockImplementation()!;
    get.mockImplementation(async(...args)=>{const response=await original(...args);if(args[0]==="/players"&&args[1].offset>0)response.data[0].id=1;return response;});
    const {result}=renderHook(()=>useDraftPlayerPool({season:2026,fetchAll:true}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isError).toBe(true));expect(String(result.current.error)).toContain("inconsistent");
  });
  it("an older request cannot overwrite a changed season",async()=>{
    setup(1);const original=get.getMockImplementation()!;let finish:()=>void=()=>{};let oldSignal:AbortSignal|undefined;
    get.mockImplementation(async(...args)=>{if(args[0]==="/players"&&args[1].season===2025){oldSignal=args[2];await new Promise<void>(resolve=>{finish=resolve;});const response=await original(...args);return {...response,ranking_season:2025};}return original(...args);});
    const {result,rerender}=renderHook(({season})=>useDraftPlayerPool({season}),{initialProps:{season:2025},wrapper:wrapper()});
    await waitFor(()=>expect(oldSignal).toBeDefined());rerender({season:2026});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));
    expect(oldSignal?.aborted).toBe(true);await act(async()=>{finish();});
    expect(result.current.data?.ranking_season).toBe(2026);
  });
  it("keeps the last valid catalog when a refresh fails",async()=>{
    setup(1);const {result}=renderHook(()=>useDraftPlayerPool({season:2026}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isSuccess).toBe(true));get.mockRejectedValue(new Error("offline"));
    await act(async()=>{await result.current.refetch();});
    await waitFor(()=>expect(result.current.isError).toBe(true));expect(result.current.data?.data[0].id).toBe(1);
  });
  it("does not report a truncated catalog as complete",async()=>{
    setup();const {result}=renderHook(()=>useDraftPlayerPool({season:2026,fetchAll:true,maxPages:1}),{wrapper:wrapper()});
    await waitFor(()=>expect(result.current.isError).toBe(true));expect(result.current.data).toBeUndefined();
  });
});
