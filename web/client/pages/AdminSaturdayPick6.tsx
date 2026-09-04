import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, apiGet, apiPost, apiPut } from "@/lib/api";
import { toast } from "@/components/ui/use-toast";

type Candidate = { player_id: number; player_name: string; school: string; position: string; opponent: string; projected_points: number };
type Contest = { id: number; title: string; contest_position: string; status: string; players: Array<{ player_id: number }> };
type Review = { contest: Contest | null; candidates: Candidate[]; sponsor_draft: Record<string, string | null> | null; audit: Array<{ id: number; action: string; reason: string | null; created_at: string }> };

const optional = (value: string) => value.trim() || null;

export default function AdminSaturdayPick6() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [week, setWeek] = useState("1");
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [sponsor, setSponsor] = useState({ name: "", logo_url: "", offer_text: "", code: "", url: "", terms: "" });
  const review = useQuery<Review>({
    queryKey: ["admin", "saturday-pick-6", season, week],
    enabled: Boolean(user?.isAdmin),
    queryFn: () => apiGet<Review>("/admin/saturday-pick-6/review", { season: Number(season), week: Number(week) }),
  });
  useEffect(() => {
    const data = review.data;
    if (!data) return;
    setSelected(data.contest?.players.map((player) => player.player_id) ?? []);
    setSponsor({ name: data.sponsor_draft?.name ?? "", logo_url: data.sponsor_draft?.logo_url ?? "", offer_text: data.sponsor_draft?.offer_text ?? "", code: data.sponsor_draft?.code ?? "", url: data.sponsor_draft?.url ?? "", terms: data.sponsor_draft?.terms ?? "" });
  }, [review.data]);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "saturday-pick-6"] });
  const prepare = useMutation({
    mutationFn: () => apiPost<Review>("/admin/saturday-pick-6/prepare", { season: Number(season), week_number: Number(week), reason: optional(reason) }),
    onSuccess: () => { toast({ title: "Pick 6 draft prepared" }); invalidate(); },
    onError: (error) => toast({ title: "Could not prepare draft", description: error instanceof ApiError ? error.message : "Try again.", variant: "destructive" }),
  });
  const save = useMutation({
    mutationFn: () => {
      const contest = review.data?.contest;
      if (!contest) throw new Error("Prepare the contest first.");
      if (selected.length !== 6) throw new Error("Select exactly six eligible players.");
      if (reason.trim().length < 3) throw new Error("Enter an audit reason of at least three characters.");
      return apiPut<Review>(`/admin/saturday-pick-6/${contest.id}/review`, { featured_player_ids: selected, title: contest.title, sponsor_name: optional(sponsor.name), sponsor_logo_url: optional(sponsor.logo_url), sponsor_offer_text: optional(sponsor.offer_text), sponsor_code: optional(sponsor.code), sponsor_url: optional(sponsor.url), sponsor_terms: optional(sponsor.terms), reason: reason.trim() });
    },
    onSuccess: () => { toast({ title: "Review saved", description: "The contest is still unpublished." }); invalidate(); },
    onError: (error) => toast({ title: "Review not saved", description: error instanceof Error ? error.message : "Try again.", variant: "destructive" }),
  });
  const publish = useMutation({
    mutationFn: () => {
      const contest = review.data?.contest;
      if (!contest) throw new Error("Prepare the contest first.");
      return apiPost(`/admin/saturday-pick-6/${contest.id}/publish`, { reason: optional(reason) });
    },
    onSuccess: () => { toast({ title: "Contest published" }); invalidate(); },
    onError: (error) => toast({ title: "Publish failed", description: error instanceof Error ? error.message : "Try again.", variant: "destructive" }),
  });
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const toggle = (playerId: number) => setSelected((current) => current.includes(playerId) ? current.filter((id) => id !== playerId) : current.length < 6 ? [...current, playerId] : current);

  if (!user?.isAdmin) return <main className="mx-auto max-w-5xl px-6 py-10"><h1 className="text-2xl font-black text-red-200">Admin access required</h1></main>;
  const contest = review.data?.contest;
  const editable = contest?.status === "DRAFT" || contest?.status === "SCHEDULED";
  return <main className="mx-auto w-full max-w-6xl space-y-6 px-6 py-8"><header><p className="text-xs font-black uppercase tracking-[0.2em] text-sky-300">Sponsor Operations</p><h1 className="mt-2 text-4xl font-black text-slate-50">Saturday Pick 6 Review</h1><p className="mt-2 text-slate-400">Select exactly six eligible players, approve sponsor content, and retain an auditable release decision.</p></header><section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5"><div className="grid gap-3 md:grid-cols-3"><Input aria-label="Season" value={season} onChange={(event) => setSeason(event.target.value)} /><Input aria-label="Week" value={week} onChange={(event) => setWeek(event.target.value)} /><Input aria-label="Audit reason" placeholder="Audit reason" value={reason} onChange={(event) => setReason(event.target.value)} /></div><div className="mt-4 flex gap-3"><Button onClick={() => prepare.mutate()} disabled={prepare.isPending}>Prepare draft</Button><Button variant="outline" onClick={() => review.refetch()}>Refresh</Button></div></section>{contest ? <><section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5"><p className="text-xs font-black uppercase tracking-[0.16em] text-sky-300">{contest.status} · {contest.contest_position} · {selected.length}/6</p><div className="mt-4 grid gap-2 md:grid-cols-2">{review.data?.candidates.map((candidate) => <button key={candidate.player_id} type="button" disabled={!editable} onClick={() => toggle(candidate.player_id)} className={`rounded-xl border p-3 text-left ${selectedSet.has(candidate.player_id) ? "border-sky-300 bg-sky-500/15" : "border-slate-700"}`}><strong>{candidate.player_name}</strong><span className="ml-2 text-sm text-slate-400">{candidate.school} vs {candidate.opponent}</span><span className="float-right font-black text-sky-200">{candidate.projected_points.toFixed(1)}</span></button>)}</div></section><section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5"><h2 className="text-xl font-black text-slate-50">West Georgia Cornhole sponsor content</h2><p className="mt-1 text-sm text-slate-400">Winner codes stay server-side until verified final results.</p><div className="mt-4 grid gap-3 md:grid-cols-2">{(["name", "logo_url", "offer_text", "code", "url"] as const).map((key) => <Input key={key} aria-label={key} placeholder={key.replaceAll("_", " ")} value={sponsor[key]} disabled={!editable} onChange={(event) => setSponsor({ ...sponsor, [key]: event.target.value })} />)}</div><Textarea className="mt-3" aria-label="Sponsor terms" placeholder="Sponsor terms" value={sponsor.terms} disabled={!editable} onChange={(event) => setSponsor({ ...sponsor, terms: event.target.value })} /><div className="mt-4 flex gap-3"><Button onClick={() => save.mutate()} disabled={!editable || save.isPending}>Save review</Button><Button onClick={() => publish.mutate()} disabled={!editable || publish.isPending}>Publish approved contest</Button></div></section><section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5"><h2 className="text-xl font-black text-slate-50">Audit trail</h2>{review.data?.audit.map((row) => <p key={row.id} className="mt-2 text-sm text-slate-300"><strong>{row.action}</strong> · {new Date(row.created_at).toLocaleString()} {row.reason ? `· ${row.reason}` : ""}</p>)}</section></> : <p className="rounded-3xl border border-dashed border-slate-700 p-8 text-slate-400">No prepared contest. Refresh projections and availability, then prepare the weekly draft.</p>}</main>;
}
