import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Loader2, LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useJoinMockDraft } from "@/hooks/use-mock-drafts";
import { extractMockInviteToken } from "@/lib/url";

export default function JoinMockDraft() {
  const navigate = useNavigate();
  const { inviteToken } = useParams();
  const [searchParams] = useSearchParams();
  const joinMutation = useJoinMockDraft();
  const [inviteCode, setInviteCode] = useState(() => extractMockInviteToken(inviteToken || searchParams.get("code") || "") || "");
  const [teamName, setTeamName] = useState("");

  const normalizedInviteCode = useMemo(() => extractMockInviteToken(inviteCode) || "", [inviteCode]);
  const canJoin = normalizedInviteCode.length >= 6 && !joinMutation.isPending;

  return (
    <div className="mx-auto max-w-xl py-8">
      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader>
          <CardTitle className="text-3xl font-black uppercase text-foreground">Join Mock Draft</CardTitle>
          <p className="text-sm font-semibold text-muted-foreground">Accounts are required. Joining closes once the scheduled draft starts.</p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label>Invite Code</Label>
            <Input
              value={inviteCode}
              onChange={(event) => setInviteCode(event.target.value)}
              placeholder="Paste invite link or token"
              className="font-black tracking-[0.08em]"
            />
          </div>
          <div className="space-y-2">
            <Label>Team Name Optional</Label>
            <Input value={teamName} onChange={(event) => setTeamName(event.target.value)} placeholder="My Team" />
          </div>
          {joinMutation.error ? (
            <p className="text-sm font-semibold text-red-300">{joinMutation.error instanceof Error ? joinMutation.error.message : "Unable to join mock draft."}</p>
          ) : null}
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => navigate("/draft")}>Cancel</Button>
            <Button
              disabled={!canJoin}
              className="bg-gradient-to-r from-emerald-300 to-cyan-400 text-slate-950"
              onClick={() =>
                joinMutation.mutate(
                  { invite_code: normalizedInviteCode, team_name: teamName.trim() || null },
                  { onSuccess: (payload) => navigate(`/draft/mock/${payload.id}/lobby`) }
                )
              }
            >
              {joinMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogIn className="mr-2 h-4 w-4" />}
              Join Draft
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
