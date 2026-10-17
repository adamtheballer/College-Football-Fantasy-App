import { Youtube } from "lucide-react";
import type { ChallengeSponsor } from "@/hooks/use-weekly-challenges";

/** The server resolves sponsorship from the displayed round, including history. */
export function WeeklyChallengeSponsor({ sponsor }: { sponsor?: ChallengeSponsor | null }) {
  if (!sponsor) return null;
  return (
    <aside aria-label={`Week ${sponsor.week} sponsor`} className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card p-3 sm:gap-4 sm:p-4">
      <img src={sponsor.logo_url} alt={`${sponsor.name} logo`} width={64} height={64} className="h-16 w-16 shrink-0 rounded-md object-contain" />
      <div className="min-w-0 flex-1 basis-40">
        <p className="cfb-micro-label text-primary">Official Week {sponsor.week} Sponsor</p>
        <p className="mt-1 text-sm font-bold sm:text-base">{sponsor.label}</p>
        <p className="mt-1 text-xs text-muted-foreground">{sponsor.tagline}</p>
      </div>
      <a href={sponsor.youtube_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-bold text-primary hover:bg-primary/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
        <Youtube aria-hidden="true" className="h-4 w-4 shrink-0" />
        Watch on YouTube
      </a>
    </aside>
  );
}
