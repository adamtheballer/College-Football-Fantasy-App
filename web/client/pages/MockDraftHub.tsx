import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Search, Trophy, Users, UserCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateMockDraft, useJoinMockDraftByCode, usePreviewMockDraft } from "@/hooks/use-mock-draft";

export default function MockDraftHub() {
  const navigate = useNavigate();
  const createMutation = useCreateMockDraft();
  const previewMutation = usePreviewMockDraft();
  const joinMutation = useJoinMockDraftByCode();
  const [managerCount, setManagerCount] = useState<"4" | "6" | "8" | "10" | "12">("12");
  const [pickTimer, setPickTimer] = useState("90");
  const [inviteCode, setInviteCode] = useState("");

  const preview = previewMutation.data;
  const loading = createMutation.isPending || joinMutation.isPending;

  const multiplayerSessionName = useMemo(() => `Public Mock Draft ${managerCount} Team Room`, [managerCount]);
  const singlePlayerSessionName = useMemo(() => `Single Player Mock Draft ${managerCount} Team Room`, [managerCount]);

  return (
    <div className="mx-auto max-w-6xl py-10 space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader className="space-y-4">
            <div className="inline-flex w-fit items-center gap-3 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100">
              <Trophy className="h-4 w-4" />
              Multiplayer Mock Draft
            </div>
            <CardTitle className="text-5xl font-black italic uppercase text-foreground">
              Choose your
              <span className="block bg-gradient-to-r from-cyan-300 via-blue-300 to-emerald-200 bg-clip-text text-transparent">
                mock draft mode
              </span>
            </CardTitle>
            <p className="max-w-2xl text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground/80">
              Start a public multiplayer room with a long secure invite code, or launch a single-player mock that auto-fills the rest of the league with CPU managers immediately.
            </p>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Seats", value: managerCount, tone: "from-cyan-500/20 to-blue-500/10" },
              { label: "Pick Clock", value: `${pickTimer}s`, tone: "from-violet-500/20 to-fuchsia-500/10" },
              { label: "Seat Fill", value: "120s", tone: "from-emerald-500/20 to-teal-500/10" },
              { label: "Invite Code", value: "20 Char", tone: "from-amber-500/20 to-rose-500/10" },
            ].map((item) => (
              <div key={item.label} className={`rounded-[1.5rem] border border-white/10 bg-gradient-to-br ${item.tone} p-5`}>
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/80">{item.label}</p>
                <p className="mt-3 text-3xl font-black text-foreground">{item.value}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="rounded-[2rem] border-white/10 bg-card/50">
            <CardHeader>
              <CardTitle className="text-[12px] font-black uppercase tracking-[0.28em] text-primary">Public Multiplayer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/80">Manager Count</Label>
                <Select value={managerCount} onValueChange={(value: "4" | "6" | "8" | "10" | "12") => setManagerCount(value)}>
                  <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.04] text-sm font-black uppercase tracking-[0.16em]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[4, 6, 8, 10, 12].map((size) => (
                      <SelectItem key={size} value={String(size)}>{size} Managers</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/80">Pick Timer</Label>
                <Select value={pickTimer} onValueChange={setPickTimer}>
                  <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.04] text-sm font-black uppercase tracking-[0.16em]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[45, 60, 90, 120].map((seconds) => (
                      <SelectItem key={seconds} value={String(seconds)}>{seconds} seconds</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                className="h-12 w-full rounded-2xl bg-gradient-to-r from-cyan-400 to-blue-500 text-[11px] font-black uppercase tracking-[0.24em] text-slate-950"
                disabled={loading}
                onClick={() =>
                  createMutation.mutate(
                    {
                      manager_count: Number(managerCount) as 4 | 6 | 8 | 10 | 12,
                      pick_timer_seconds: Number(pickTimer),
                      name: multiplayerSessionName,
                      mode: "public_multiplayer",
                    },
                    {
                      onSuccess: (payload) => navigate(`/mock-drafts/${payload.id}/lobby`),
                    }
                  )
                }
              >
                {createMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                <Users className="mr-2 h-4 w-4" />
                Create Public Lobby
              </Button>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/75">
                This creates a public multiplayer mock draft with a 20-character invite code made from secure random letters and numbers.
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-[2rem] border-white/10 bg-card/50">
            <CardHeader>
              <CardTitle className="text-[12px] font-black uppercase tracking-[0.28em] text-primary">Single Player</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-4">
                <p className="text-sm font-black text-foreground">Draft against auto managers immediately</p>
                <p className="mt-2 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/80">
                  The rest of the room fills with CPU managers right away. You skip the public seat-claim lobby and go straight into the mock draft preview room.
                </p>
              </div>
              <Button
                className="h-12 w-full rounded-2xl bg-gradient-to-r from-emerald-300 to-cyan-400 text-[11px] font-black uppercase tracking-[0.24em] text-slate-950"
                disabled={loading}
                onClick={() =>
                  createMutation.mutate(
                    {
                      manager_count: Number(managerCount) as 4 | 6 | 8 | 10 | 12,
                      pick_timer_seconds: Number(pickTimer),
                      name: singlePlayerSessionName,
                      mode: "single_player",
                    },
                    {
                      onSuccess: (payload) => navigate(`/mock-drafts/${payload.id}/room`),
                    }
                  )
                }
              >
                {createMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                <UserCircle2 className="mr-2 h-4 w-4" />
                Start Single-Player Mock
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-[2rem] border-white/10 bg-card/50">
            <CardHeader>
              <CardTitle className="text-[12px] font-black uppercase tracking-[0.28em] text-primary">Join Public Lobby By Code</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={inviteCode}
                  onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                  placeholder="ENTER INVITE CODE"
                  className="h-12 rounded-xl border-white/10 bg-white/[0.04] pl-11 text-sm font-black uppercase tracking-[0.22em]"
                />
              </div>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="h-11 flex-1 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                  onClick={() => previewMutation.mutate(inviteCode.trim().toUpperCase())}
                  disabled={previewMutation.isPending || inviteCode.trim().length < 4}
                >
                  Preview
                </Button>
                <Button
                  className="h-11 flex-1 rounded-xl bg-gradient-to-r from-emerald-300 to-cyan-400 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950"
                  onClick={() =>
                    joinMutation.mutate(inviteCode.trim().toUpperCase(), {
                      onSuccess: (payload) => navigate(`/mock-drafts/${payload.id}/lobby`),
                    })
                  }
                  disabled={joinMutation.isPending || inviteCode.trim().length < 4}
                >
                  {joinMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Join Lobby
                </Button>
              </div>
              {preview ? (
                <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-4 space-y-2">
                  <p className="text-sm font-black text-foreground">{preview.name}</p>
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                    {preview.joined_count}/{preview.manager_count} seats filled • {preview.pick_timer_seconds}s timer • {preview.status}
                  </p>
                </div>
              ) : null}
              {previewMutation.error ? (
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                  {previewMutation.error instanceof Error ? previewMutation.error.message : "Unable to preview mock draft."}
                </p>
              ) : null}
              {joinMutation.error ? (
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                  {joinMutation.error instanceof Error ? joinMutation.error.message : "Unable to join mock draft."}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
