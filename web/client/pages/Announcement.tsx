import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
export default function Announcement() {
  const { announcementId } = useParams();
  const id = Number(announcementId);
  const query = useQuery({ queryKey: ["announcement", id], enabled: Number.isSafeInteger(id) && id > 0, queryFn: () => apiGet<{ title: string; body: string }>(`/notifications/announcements/${id}`) });
  return <main className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6"><Link to="/alerts" className="text-primary underline">Back to Alerts</Link>{query.data ? <article className="space-y-4 rounded-lg border border-border bg-card p-5"><h1 className="text-2xl font-black">{query.data.title}</h1><p className="whitespace-pre-wrap">{query.data.body}</p></article> : <p role={query.isError ? "alert" : "status"}>{query.isError || !Number.isSafeInteger(id) || id <= 0 ? "This announcement is no longer available." : "Loading announcement…"}</p>}</main>;
}
