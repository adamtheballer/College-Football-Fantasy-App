// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Challenge, ChallengeKind } from "@/hooks/use-weekly-challenges";
import { ChallengeShare } from "./ChallengeShare";
const mocks=vi.hoisted(()=>({get:vi.fn(),write:vi.fn(),copy:vi.fn()}));
vi.mock("@/hooks/use-auth",()=>({useAuth:()=>({user:{id:7}})}));
vi.mock("@/lib/api",()=>({apiGet:mocks.get,apiChallengeWrite:mocks.write}));
const challenge=(kind:ChallengeKind,state="Open")=>({id:77,kind,name:"Test competition",state,season:2026,week:8,server_now:"2026-10-20T18:00:00Z",lock_at:"2026-10-24T18:00:00Z",experience:null,entry:{status:"submitted",selections:[{team:"Secret choice",game_id:1}]},players:[]} as Challenge);
function show(c:Challenge){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ChallengeShare challenge={c}/></MemoryRouter></QueryClientProvider>);}
beforeEach(()=>{vi.clearAllMocks();mocks.copy.mockResolvedValue(undefined);mocks.write.mockResolvedValue({recorded:true});Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:mocks.copy}});Object.defineProperty(navigator,"share",{configurable:true,value:undefined});localStorage.clear();});
afterEach(cleanup);
describe("safe sharing for the five existing competitions",()=>{
 it.each(["slate12","upset","fantasy5","lock","duels"] as const)("shares %s without revealing selections before lock",async kind=>{
  show(challenge(kind));fireEvent.click(screen.getByRole("button",{name:"Share"}));await waitFor(()=>expect(mocks.copy).toHaveBeenCalledTimes(1));
  const text=mocks.copy.mock.calls[0][0];expect(text).toContain("/weekly-challenges/77");expect(text).toContain("Week 8");expect(text).not.toContain("Secret choice");expect(screen.queryByRole("checkbox")).toBeNull();expect(mocks.get).not.toHaveBeenCalled();
 });
 it("includes only the caller's finalized result in a result card",async()=>{
  mocks.get.mockResolvedValue({my_result:{status:"final",raw_points:12,challenge_points:3,rank:2}});show(challenge("slate12","Closed — Final"));await waitFor(()=>expect(mocks.get).toHaveBeenCalled());
  await waitFor(()=>expect(screen.getByText("Your final result: 12 points · Rank #2")).toBeTruthy());
  fireEvent.click(screen.getByRole("button",{name:"Share"}));
  await waitFor(()=>expect(mocks.copy).toHaveBeenCalledTimes(1));
  expect(mocks.copy.mock.calls[0][0]).toContain("12 result points · 3 championship points · Rank #2");
 });
});
