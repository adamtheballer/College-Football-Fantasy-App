import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiPost } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
type Announcement = { id: number; title: string; body: string; audience: Record<string, unknown>; status: string; dispatch: Record<string, number>; recipient_count?: number };
export default function AdminAnnouncements() {
  const { user } = useAuth();
  const client = useQueryClient();
  const list = useQuery({ queryKey: ["admin-announcements", user?.id], enabled: Boolean(user?.isAdmin), queryFn: () => apiGet<{ data: Announcement[] }>("/notifications/announcements/admin"), refetchInterval: 15_000 });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [conference, setConference] = useState("");
  const [playerId, setPlayerId] = useState("");
  const [preview, setPreview] = useState<Announcement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!user?.isAdmin) return <Navigate to="/" replace />;
  const prepare = async () => {
    setBusy(true); setError(null); setPreview(null);
    try {
      const draft = await apiPost<Announcement>("/notifications/announcements/admin", { title, body, conference: conference || null, player_id: playerId ? Number(playerId) : null });
      setPreview(await apiGet<Announcement>(`/notifications/announcements/admin/${draft.id}/preview`));
      await client.invalidateQueries({ queryKey: ["admin-announcements"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to prepare announcement."); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!preview) return;
    setBusy(true); setError(null);
    try {
      await apiPost(`/notifications/announcements/admin/${preview.id}/confirm`, { confirm: true });
      setPreview(null); setTitle(""); setBody("");
      await client.invalidateQueries({ queryKey: ["admin-announcements"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to confirm announcement."); }
    finally { setBusy(false); }
  };
  return <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
    <h1 className="text-2xl font-black">News announcements</h1>
    <p className="text-sm text-muted-foreground">Only users who opt in to major news can receive these phone alerts. Previewing saves a draft; sending requires confirmation.</p>
    <section className="space-y-4 rounded-lg border border-border bg-card p-4">
      <label className="block text-sm">Title<Input aria-label="Announcement title" maxLength={120} value={title} disabled={busy} onChange={(event) => { setTitle(event.target.value); setPreview(null); }} /></label>
      <label className="block text-sm">Message<textarea aria-label="Announcement message" maxLength={400} value={body} disabled={busy} onChange={(event) => { setBody(event.target.value); setPreview(null); }} className="mt-1 min-h-24 w-full rounded-md border border-border bg-background p-3" /></label>
      <label className="block text-sm">Audience<select aria-label="Announcement audience" value={conference} disabled={busy} onChange={(event) => { setConference(event.target.value); setPreview(null); }} className="ml-3 rounded-md border border-border bg-background p-2"><option value="">All opted-in users</option>{["SEC", "ACC", "BIG10", "BIG12"].map((item) => <option key={item} value={item}>Managers with {item} players</option>)}</select></label>
      <label className="block text-sm">Optional rostered player ID<Input aria-label="Audience player ID" type="number" min={1} value={playerId} disabled={busy} onChange={(event) => { setPlayerId(event.target.value); setPreview(null); }} /></label>
      <Button disabled={busy || !title.trim() || !body.trim()} onClick={() => void prepare()}>Preview announcement</Button>
    </section>
    {preview ? <section aria-label="Announcement preview" className="space-y-3 rounded-lg border border-primary/40 bg-card p-4"><h2 className="font-bold">{preview.title}</h2><p>{preview.body}</p><p className="text-sm">{preview.recipient_count} eligible recipients. Preferences and audience will be checked again at delivery.</p><Button disabled={busy || !preview.recipient_count} onClick={() => void confirm()}>Confirm and queue announcement</Button></section> : null}
    {error ? <p role="alert" className="text-red-300">{error}</p> : null}
    {list.isError ? <p role="alert">Unable to load dispatch status.</p> : null}
    <section className="space-y-3"><h2 className="font-bold">Dispatch status</h2>{list.data?.data.map((item) => <article key={item.id} className="rounded-lg border border-border bg-card p-4"><h3 className="font-bold">{item.title}</h3><p className="text-sm text-muted-foreground">{item.status} · {Object.entries(item.dispatch).map(([state, count]) => `${state}: ${count}`).join(" · ") || "No deliveries queued"}</p><p className="text-xs text-muted-foreground">Provider acceptance does not confirm phone display.</p>{item.status === "draft" ? <Button variant="outline" disabled={busy} onClick={() => void apiGet<Announcement>(`/notifications/announcements/admin/${item.id}/preview`).then(setPreview).catch(() => setError("Unable to load preview."))}>Review draft</Button> : null}</article>)}</section>
  </main>;
}
