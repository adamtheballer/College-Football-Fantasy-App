import {describe,it,expect} from "vitest";
import {buildDraftBoard,getDraftPlayerIdentityKey,type DraftConfig} from "./draftRankings";
import type {Player} from "@/types/player";
const config:DraftConfig={leagueSize:12,totalRosterSpots:13,rosterSlots:{QB:1,RB:2,WR:2,TE:1,K:1,BE:5,IR:0}};
const player=(id:number,rank:number,points:number|null,extra:Partial<Player>={}):Player=>({id,name:`Player ${id}`,school:"Texas",pos:"WR",conf:"SEC",rank:0,adp:0,posRank:null,rostered:0,status:"HEALTHY",projection:{fpts:0},history:[],analysis:"",masterDraftRank:rank,draftProjectedPoints:points,draftProjectionMissing:points===null,draftRankingVersion:"version-a",...extra});
describe("versioned backend draft-board adapter",()=>{
  it("uses numeric overall ranks and stable IDs without reranking a filtered pool",()=>{
    const full=buildDraftBoard([player(119,119,200),player(20,20,0),player(10,10,100),player(2,2,100)],config);
    expect(full.map(p=>p.id)).toEqual([2,10,20,119]);
    expect(buildDraftBoard([full[1],full[3]],config).map(p=>p.masterDraftRank)).toEqual([10,119]);
  });
  it("preserves tied source projections and differentiates unknown from zero",()=>{
    const board=buildDraftBoard([player(1,1,20),player(2,2,20),player(3,3,0),player(4,4,null)],config);
    expect(board.map(p=>p.projectedPoints)).toEqual([20,20,0,0]);
    expect(board.map(p=>p.projectionMissing)).toEqual([false,false,false,true]);
    expect(board[0].projection.fpts).toBe(0); // weekly forecast is not overwritten by season points
  });
  it("does not fabricate ADP or select ambiguous names by their projections",()=>{
    const board=buildDraftBoard([player(1,1,20,{name:"Same Name"}),player(2,2,200,{name:"Same Name"})],config);
    expect(board.map(p=>p.id)).toEqual([1,2]);
    expect(board.every(p=>p.adpEstimate===0)).toBe(true);
    expect(buildDraftBoard([player(1,1,20,{sheetAdp:10})],config)[0].adpEstimate).toBe(10);
  });
  it("withholds an unversioned/invalid server rank and retains out and late-page players",()=>{
    expect(buildDraftBoard([player(1,0,20),player(2,1,20,{draftRankingVersion:null})],config)).toEqual([]);
    const board=buildDraftBoard(Array.from({length:620},(_,i)=>player(i+1,i+1,20,{status:i===619?"OUT":"HEALTHY"})),config);
    expect(board).toHaveLength(620);expect(board[619].id).toBe(620);expect(board[619].status).toBe("OUT");
  });
  it("retains the name/school/position identity utility for completed pick reconciliation",()=>{
    expect(getDraftPlayerIdentityKey({name:"José  Smith",school:"Texas",position:"WR"})).toBe("jose smith|texas|wr");
  });
});
