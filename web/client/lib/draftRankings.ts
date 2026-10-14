import { Player } from "@/types/player";

export type DraftRosterSlots = {
  QB: number;
  RB: number;
  WR: number;
  TE: number;
  K: number;
  BE: number;
  IR: number;
};

export type DraftConfig = {
  leagueSize: number;
  rosterSlots: DraftRosterSlots;
  totalRosterSpots?: number;
};

export type DraftPlayer = Player & {
  draftRank: number;
  masterDraftRank: number;
  sourceBoardRank: number | null;
  adpRank: number;
  adpEstimate: number;
  projectedPoints: number;
  projectionMissing?: boolean;
  tier: number;
  tprScore: number;
  marScore: number;
  finalDraftScore: number;
  cfb27Overall: number | null;
  cfb27TalentScore: number;
};

const valid = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value > 0;
export const getDraftPlayerIdentityKey = (player: {id?:number;name?:string|null;playerName?:string|null;school?:string|null;pos?:string|null;position?:string|null}) => [player.name ?? player.playerName,player.school,player.pos ?? player.position].map(value => (value ?? "").normalize("NFKD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^a-z0-9]+/g," ").trim()).join("|");
export const getEarliestKickerDraftRank = (config: DraftConfig) => Math.max(100, config.leagueSize * (config.totalRosterSpots ?? Object.values(config.rosterSlots).reduce((a,b)=>a+b,0)) - config.leagueSize * 2);

/** Consume the backend's versioned positional-value policy; never rerank a page. */
export const buildDraftBoard = (players: Player[], _config: DraftConfig): DraftPlayer[] => {
  const byId = new Map<number, Player>();
  for (const player of players) if (valid(player.masterDraftRank) && player.draftRankingVersion) byId.set(player.id,player);
  return [...byId.values()].sort((a,b)=>(a.masterDraftRank! - b.masterDraftRank!) || a.id-b.id).map(player=>{
    const points = typeof player.draftProjectedPoints === "number" && Number.isFinite(player.draftProjectedPoints) ? player.draftProjectedPoints : 0;
    return {...player,draftRank:player.masterDraftRank!,masterDraftRank:player.masterDraftRank!,sourceBoardRank:player.draftSourceRank ?? null,adpRank:valid(player.sheetAdp)?player.sheetAdp:0,adpEstimate:valid(player.sheetAdp)?player.sheetAdp:0,projectedPoints:points,projectionMissing:player.draftProjectionMissing ?? player.draftProjectedPoints == null,tier:player.draftTier ?? 1,tprScore:0,marScore:0,finalDraftScore:player.draftFinalScore ?? 0,cfb27Overall:player.cfb27Overall ?? null,cfb27TalentScore:player.draftTalentScore ?? .5};
  });
};
