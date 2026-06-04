import { useNavigate, useParams } from "react-router-dom";
import { Clipboard, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMockDraftHistory } from "@/hooks/use-mock-drafts";

export default function MockDraftResults() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: history, isLoading, error } = useMockDraftHistory(parsedMockDraftId, Boolean(parsedMockDraftId));

  if (isLoading) {
    return <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading results...</div>;
  }
  if (!history) {
    return <div className="py-16 text-center text-red-300">{error instanceof Error ? error.message : "Results unavailable."}</div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-8">
      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader>
          <CardTitle className="text-3xl font-black uppercase text-foreground">{history.draft_name}</CardTitle>
          <p className="text-sm font-semibold text-muted-foreground">{history.pick_count} picks completed</p>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button variant="outline" onClick={() => navigator.clipboard?.writeText(history.plain_text)}>
            <Clipboard className="mr-2 h-4 w-4" />
            Copy History
          </Button>
          <Button className="bg-cyan-300 text-slate-950" onClick={() => navigate("/draft")}>Back To Draft Tab</Button>
        </CardContent>
      </Card>
      {history.picks_by_round.map((round) => (
        <Card key={round.round} className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader><CardTitle className="text-[12px] font-black uppercase tracking-[0.22em] text-primary">Round {round.round}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {round.picks.map((pick) => (
              <div key={pick.id} className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[90px_minmax(0,1fr)_minmax(0,1fr)]">
                <p className="font-black text-muted-foreground">{pick.round_number}.{pick.round_pick}</p>
                <p className="font-black text-foreground">{pick.player_name} ({pick.player_position})</p>
                <p className="text-sm font-semibold text-muted-foreground">{pick.team_name}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
