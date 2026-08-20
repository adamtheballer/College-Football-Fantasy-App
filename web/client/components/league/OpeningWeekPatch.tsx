import { Flag } from "lucide-react";

export function OpeningWeekPatch({ week }: { week: number | null | undefined }) {
  if (week !== 1) return null;

  return (
    <div
      data-testid="opening-week-patch"
      className="flex items-center justify-center gap-2 border-b border-cfb-brand/35 bg-cfb-brand/[0.08] px-3 py-2 text-center"
    >
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-cfb-brand/50 bg-cfb-canvas text-cfb-brand">
        <Flag className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
      <div className="min-w-0 text-left">
        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">Opening Week</p>
        <p className="text-[9px] font-semibold text-cfb-text-secondary">Season kickoff · Week 1</p>
      </div>
    </div>
  );
}
