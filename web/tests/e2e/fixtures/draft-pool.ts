/** Fixtures must publish the same versioned draft contract as FastAPI. */
export function canonicalDraftPool<T extends {id:number;board_rank?:number;sheet_projected_season_points?:number}>(players:T[],extra:Record<string,unknown>={}) {
 return {data:players.map((player,index)=>({...player,master_draft_rank:player.board_rank??index+1,draft_projected_points:player.sheet_projected_season_points??null,draft_projection_missing:player.sheet_projected_season_points==null,draft_ranking_version:'isolated-browser-fixture'})),total:players.length,limit:100,offset:0,ranking_version:'isolated-browser-fixture',ranking_season:2026,ranking_week:7,...extra};
}
