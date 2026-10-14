// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {DraftBoardSortControl,sortDraftBoardPlayers} from "./DraftBoardSortControl";
import type {DraftPlayer} from "@/lib/draftRankings";
afterEach(cleanup);
const p=(id:number,rank:number,adp:unknown,points:number,missing=false)=>({id,masterDraftRank:rank,sheetAdp:adp,projectedPoints:points,projectionMissing:missing}) as DraftPlayer;
describe("shared real/mock draft sorting",()=>{
  it("orders numeric source ADP ascending and puts invalid values last with ID ties",()=>{
    const pool=[p(119,1,"119",20),p(20,2,"20",20),p(10,3,"10",20),p(2,4,"2",20),p(8,5,NaN,1000),p(7,6,0,1000),p(6,7,null,1000)];
    expect(sortDraftBoardPlayers(pool,"adp").map(p=>p.id)).toEqual([2,10,20,119,6,7,8]);
  });
  it("keeps zero forecasts above unknown and sorts valid points descending",()=>{
    expect(sortDraftBoardPlayers([p(1,1,0,0,true),p(2,2,0,0),p(3,3,0,20),p(4,4,0,20)],"projected_points").map(p=>p.id)).toEqual([3,4,2,1]);
  });
  it("filters without renumbering source ranks or mutating a deliberately ordered queue",()=>{
    const pool=[p(3,119,1,500),p(2,20,1,400),p(1,2,1,10)],queue=[3,1,2];
    expect(sortDraftBoardPlayers(pool.filter(p=>p.id!==2),"draft_rank").map(p=>p.masterDraftRank)).toEqual([2,119]);
    expect(pool.map(p=>p.id)).toEqual([3,2,1]);expect(queue).toEqual([3,1,2]);
  });
  it("makes the selected ordering explicit",()=>{
    const change=vi.fn();render(<DraftBoardSortControl value="draft_rank" onChange={change}/>);
    fireEvent.change(screen.getByLabelText("Draft board sort"),{target:{value:"adp"}});expect(change).toHaveBeenCalledWith("adp");
    expect(screen.getByRole("option",{name:"Overall draft rank"})).toBeTruthy();
  });
});
