import type { DraftPlayer } from "@/lib/draftRankings";
export type DraftBoardSort = "draft_rank" | "adp" | "projected_points";
const numeric = (value: unknown) => {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const positive = (value: unknown) => { const parsed=numeric(value);return parsed !== null && parsed > 0 ? parsed : null; };
export function sortDraftBoardPlayers(players: DraftPlayer[], mode: DraftBoardSort): DraftPlayer[] {
  return [...players].sort((left,right)=>{
    if(mode==="adp") {
      const a=positive(left.sheetAdp),b=positive(right.sheetAdp);
      return Number(a===null)-Number(b===null) || (a??Infinity)-(b??Infinity) || left.id-right.id;
    }
    if(mode==="projected_points") {
      const a=left.projectionMissing ? null:numeric(left.projectedPoints),b=right.projectionMissing ? null:numeric(right.projectedPoints);
      return Number(a===null)-Number(b===null) || (b??-Infinity)-(a??-Infinity) || left.id-right.id;
    }
    return (positive(left.masterDraftRank)??Infinity)-(positive(right.masterDraftRank)??Infinity) || left.id-right.id;
  });
}
export function DraftBoardSortControl({value,onChange}:{value:DraftBoardSort;onChange:(value:DraftBoardSort)=>void}) {
  return <label className="flex shrink-0 items-center gap-2 text-xs text-cfb-text-secondary">Sort<select aria-label="Draft board sort" className="h-9 max-w-[180px] rounded-md border border-cfb-border-subtle bg-cfb-surface px-2 text-xs text-cfb-text-primary" value={value} onChange={event=>onChange(event.target.value as DraftBoardSort)}><option value="draft_rank">Overall draft rank</option><option value="adp">Source ADP</option><option value="projected_points">Season / remaining points</option></select></label>;
}
