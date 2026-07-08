import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Check, Copy, Link2, UserPlus, Users } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { useLeagueSettingsTab } from "@/hooks/use-leagues";
import { DEMO_LEAGUE_ID, createDemoLeagueSettingsResponse } from "@/lib/leaguePreviewData";

export default function LeagueInviteMembers() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const data = isDemoLeague ? createDemoLeagueSettingsResponse() : settingsQuery.data;
  const [copiedField, setCopiedField] = useState<"code" | "link" | null>(null);
  const inviteCode = data?.invite_code ?? null;
  const inviteLink = useMemo(() => {
    if (data?.invite_link) return data.invite_link;
    if (!inviteCode || typeof window === "undefined") return null;
    return `${window.location.origin}/join/${inviteCode}`;
  }, [data?.invite_link, inviteCode]);

  const copyValue = async (value: string | null | undefined, field: "code" | "link") => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedField(field);
    window.setTimeout(() => {
      setCopiedField((current) => (current === field ? null : current));
    }, 1800);
  };

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[460px] rounded-[3rem] bg-[radial-gradient(circle_at_18%_8%,rgba(56,189,248,0.2),transparent_34%),radial-gradient(circle_at_76%_0%,rgba(99,102,241,0.18),transparent_38%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Invites
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Invite Members</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Retrieve the same invite code and link created with this league. This pre-draft tab disappears after the draft is complete.
            </p>
          </div>
          <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
            <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Managers Joined</p>
            <p className="mt-1 text-2xl font-black text-sky-100">
              {data?.members?.length ?? 0}
              <span className="text-base text-slate-500"> / {String(data?.league_info?.max_teams ?? "—")}</span>
            </p>
          </div>
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
        <div className="border-b border-sky-300/10 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-sky-300/25 bg-sky-300/10 text-sky-100">
              <UserPlus className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-black text-slate-50">Share league access</h2>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                Send this to managers before the draft fills. Picks stay locked until every league slot is filled.
              </p>
            </div>
          </div>
        </div>

        {settingsQuery.isLoading && !isDemoLeague ? (
          <div className="px-6 py-10 text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
            Loading invite details...
          </div>
        ) : inviteCode ? (
          <div className="grid gap-4 p-6 lg:grid-cols-2">
            <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.04] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Invite Code</p>
              <p className="mt-3 break-all text-3xl font-black tracking-[0.08em] text-sky-100">{inviteCode}</p>
              <button
                type="button"
                onClick={() => void copyValue(inviteCode, "code")}
                className="mt-5 inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-sky-300/25 bg-sky-300/10 px-5 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100 transition hover:border-sky-300/45 hover:bg-sky-300/18"
              >
                {copiedField === "code" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copiedField === "code" ? "Copied" : "Copy Code"}
              </button>
            </div>
            <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.04] p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Invite Link</p>
              <p className="mt-3 break-all text-sm font-bold leading-6 text-slate-300">{inviteLink}</p>
              <button
                type="button"
                disabled={!inviteLink}
                onClick={() => void copyValue(inviteLink, "link")}
                className="mt-5 inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-sky-300/25 bg-sky-300/10 px-5 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100 transition hover:border-sky-300/45 hover:bg-sky-300/18 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {copiedField === "link" ? <Check className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
                {copiedField === "link" ? "Copied" : "Copy Link"}
              </button>
            </div>
          </div>
        ) : (
          <div className="px-6 py-12 text-center">
            <Users className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">Invite details are unavailable.</p>
            <p className="mt-2 text-xs font-semibold text-slate-500">
              Only the commissioner can view and share this league invite.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
