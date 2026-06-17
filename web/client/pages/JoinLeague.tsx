import React, { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Copy, Search, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiPost } from "@/lib/api";
import { buildLeagueInviteLink, extractInviteCodeFromInput } from "@/lib/invite";
import { ensureBrowserPushRegistration } from "@/lib/push";
import { LeagueDetail, LeaguePreview } from "@/types/league";
import { useAuth } from "@/hooks/use-auth";
import { useActiveLeagueId } from "@/hooks/use-active-league";

function leagueJoinErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "Unable to reach the backend API. Make sure the server is running.";
    }
    if (error.status === 401 || error.status === 403) {
      return error.message.includes("private leagues require")
        ? "You need a valid invite code to join this league."
        : "You need to sign in to join this league.";
    }
    if (error.status === 404) {
      return "Invite code not found.";
    }
    if (error.status === 409) {
      if (error.message.includes("already joined")) return "You already joined this league.";
      if (error.message.includes("full")) return "This league is full.";
      return error.message;
    }
    return error.message;
  }
  return error instanceof Error && error.message ? error.message : "Unable to join league.";
}

export default function JoinLeague() {
  const { inviteCode } = useParams();
  const queryClient = useQueryClient();
  const { isLoggedIn } = useAuth();
  const { setActiveLeagueId } = useActiveLeagueId();
  const navigate = useNavigate();
  const location = useLocation();
  const [code, setCode] = useState(inviteCode || "");
  const [preview, setPreview] = useState<LeaguePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (inviteCode) {
      setCode(inviteCode);
      handlePreview(inviteCode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inviteCode]);

  const handlePreview = async (value?: string) => {
    const invite = extractInviteCodeFromInput(value ?? code);
    if (invite.length < 6) {
      setError("Enter a valid invite code.");
      return;
    }
    setCode(invite);
    setError(null);
    setLoading(true);
    try {
      const payload = await apiPost<LeaguePreview>("/leagues/join-by-code", { invite_code: invite });
      setPreview(payload);
    } catch (err) {
      setPreview(null);
      setError(leagueJoinErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!preview) return;
    if (preview.member_count >= preview.max_teams) {
      setError("This league is full.");
      return;
    }
    const invite = extractInviteCodeFromInput(code);
    if (!isLoggedIn) {
      navigate("/login", {
        state: { from: `/join/${invite || code}` },
        replace: true,
      });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const joinedLeague = await apiPost<LeagueDetail>(`/leagues/${preview.id}/join`, {
        invite_code: invite,
      });
      void ensureBrowserPushRegistration();
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.setQueryData(["league", joinedLeague.id], joinedLeague);
      setActiveLeagueId(joinedLeague.id);
      navigate(`/league/${joinedLeague.id}`);
    } catch (err) {
      setError(leagueJoinErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    const invite = extractInviteCodeFromInput(code || inviteCode || "");
    const returnTo = invite ? `/join/${invite}` : `${location.pathname}${location.search}${location.hash}`;
    return (
      <div className="max-w-3xl mx-auto py-20 space-y-6">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12 text-center space-y-6">
          <h1 className="text-4xl font-black italic uppercase text-foreground">Sign In Required</h1>
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
            Please sign in to join a league.
          </p>
          <Button
            onClick={() => navigate("/login", { state: { from: returnTo } })}
            className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black tracking-[0.2em] uppercase"
          >
            Go to Login
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-12 space-y-8">
      <div className="space-y-3">
        <h1 className="text-6xl font-black italic uppercase text-foreground">Join League</h1>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-[0.2em]">
          Paste an invite code or full invite link to preview a league.
        </p>
      </div>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Invite Code</CardTitle>
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="pl-12 h-12 rounded-xl bg-white/5 border-border text-sm font-bold tracking-widest"
                placeholder="ENTER INVITE CODE OR LINK"
              />
            </div>
            <Button
              className="h-12 px-6 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => handlePreview()}
              disabled={loading}
            >
              Preview League
            </Button>
          </div>
          {error && <p className="text-sm font-bold text-red-400 uppercase tracking-[0.2em]">{error}</p>}
        </CardContent>
      </Card>

      {preview && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">League Preview</CardTitle>
          </CardHeader>
          <CardContent className="px-10 pb-10 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">League</p>
                <p className="text-xl font-black text-primary">{preview.name}</p>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Commissioner</p>
                <p className="text-xl font-black text-primary">{preview.commissioner_name || "Commissioner"}</p>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Members</p>
                <p className="text-xl font-black text-primary">
                  {preview.member_count}/{preview.max_teams}
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft</p>
                <p className="text-xl font-black text-primary">
                  {preview.draft_datetime_utc ? new Date(preview.draft_datetime_utc).toLocaleString() : "TBD"}
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Scoring</p>
                <p className="text-xl font-black text-primary uppercase">{preview.scoring_preset.replace(/_/g, " ")}</p>
              </div>
            </div>
            {preview.member_count >= preview.max_teams && (
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-400">
                League is full.
              </p>
            )}

            <div className="flex items-center gap-4">
              <Button
                className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={handleJoin}
                disabled={loading || preview.member_count >= preview.max_teams}
              >
                Join League
              </Button>
              <Button
                variant="outline"
                className="h-12 px-6 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={() => navigator.clipboard.writeText(buildLeagueInviteLink(code))}
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Invite Link
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {!preview && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
              <Users className="w-6 h-6 text-primary" />
            </div>
            <div>
              <p className="text-sm font-black uppercase tracking-[0.2em] text-foreground">Need a code?</p>
              <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground/60">
                Ask your commissioner to share the 20-character invite code.
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
