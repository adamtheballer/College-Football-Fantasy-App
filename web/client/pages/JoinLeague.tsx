import React, { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Copy, Loader2, Search, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiPost } from "@/lib/api";
import { ensureBrowserPushRegistration } from "@/lib/push";
import { LeagueDetail, LeaguePreview } from "@/types/league";
import { useAuth } from "@/hooks/use-auth";

export default function JoinLeague() {
  const { inviteCode } = useParams();
  const queryClient = useQueryClient();
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [code, setCode] = useState(inviteCode || "");
  const [preview, setPreview] = useState<LeaguePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [matchmakingLoading, setMatchmakingLoading] = useState(false);
  const [randomTeamCount, setRandomTeamCount] = useState("12");
  const [randomSkillMode, setRandomSkillMode] = useState<"beginner" | "pro">("beginner");
  const [matchmakingError, setMatchmakingError] = useState<string | null>(null);

  useEffect(() => {
    if (inviteCode) {
      setCode(inviteCode.toUpperCase());
      handlePreview(inviteCode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inviteCode]);

  const handlePreview = async (value?: string) => {
    const invite = (value ?? code).trim().toUpperCase();
    if (invite.length < 6) {
      setError("Enter a valid invite code.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const payload = await apiPost<LeaguePreview>("/leagues/join-by-code", { invite_code: invite });
      setPreview(payload);
    } catch (err: any) {
      setPreview(null);
      setError(err.message || "Invite code not found.");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!preview) return;
    if (preview.member_count >= preview.max_teams) {
      setError("League is already full.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const joinedLeague = await apiPost<LeagueDetail>(`/leagues/join-with-code`, {
        invite_code: code.trim().toUpperCase(),
      });
      void ensureBrowserPushRegistration();
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.setQueryData(["league", joinedLeague.id], joinedLeague);
      navigate(`/league/${joinedLeague.id}`);
    } catch (err: any) {
      setError(err.message || "Unable to join league.");
    } finally {
      setLoading(false);
    }
  };

  const handleJoinRandomLeague = async () => {
    setMatchmakingLoading(true);
    setMatchmakingError(null);
    try {
      const joinedLeague = await apiPost<LeagueDetail>("/leagues/matchmaking/join", {
        team_count: Number(randomTeamCount),
        skill_mode: randomSkillMode,
      });
      void ensureBrowserPushRegistration();
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.setQueryData(["league", joinedLeague.id], joinedLeague);

      const shouldOpenDraft =
        joinedLeague.status === "draft_scheduled" || joinedLeague.status === "draft_live";
      navigate(shouldOpenDraft ? `/league/${joinedLeague.id}/lobby` : `/league/${joinedLeague.id}`);
    } catch (err: any) {
      setMatchmakingError(err.message || "Unable to join random league.");
    } finally {
      setMatchmakingLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="max-w-3xl mx-auto py-20 space-y-6">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12 text-center space-y-6">
          <h1 className="text-4xl font-black italic uppercase text-foreground">Sign In Required</h1>
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
            Please sign in to join a league.
          </p>
          <Button onClick={() => navigate("/login")} className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black tracking-[0.2em] uppercase">
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
          Paste the 20-character invite code to join.
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
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                className="pl-12 h-12 rounded-xl bg-white/5 border-border text-sm font-bold tracking-widest uppercase"
                placeholder="ENTER INVITE CODE"
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

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Join Random League</CardTitle>
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-6">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
            Pick size + skill mode. When the room fills, draft room opens immediately and draft starts in 2 minutes.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                League Size
              </Label>
              <Select value={randomTeamCount} onValueChange={setRandomTeamCount}>
                <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.16em]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[4, 6, 8, 10, 12, 14, 16].map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size} Teams
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                Skill Mode
              </Label>
              <Select
                value={randomSkillMode}
                onValueChange={(value: "beginner" | "pro") => setRandomSkillMode(value)}
              >
                <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.16em]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="beginner">Beginner</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {matchmakingError && (
            <p className="text-sm font-bold text-red-400 uppercase tracking-[0.2em]">{matchmakingError}</p>
          )}
          <Button
            className="h-12 px-6 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
            onClick={handleJoinRandomLeague}
            disabled={matchmakingLoading}
          >
            {matchmakingLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Join Random League
          </Button>
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
                onClick={() => navigator.clipboard.writeText(code)}
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Code
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
