import { useMemo, useState } from "react";
import { Bug, Check, Copy, Mail, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";

const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL as string | undefined;

const REPORT_TYPES = ["Bug", "Data issue", "Suggestion", "Account help", "Other"];

export default function ReportBug() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [reportType, setReportType] = useState("Bug");
  const [summary, setSummary] = useState("");
  const [details, setDetails] = useState("");
  const [copied, setCopied] = useState(false);

  const report = useMemo(
    () =>
      [
        `Report type: ${reportType}`,
        `Summary: ${summary.trim() || "Not provided"}`,
        "",
        details.trim() || "No additional details provided.",
        "",
        `Account: ${user?.email ?? "Not signed in"}`,
        `Route: ${window.location.pathname}`,
        `Reported at: ${new Date().toISOString()}`,
      ].join("\n"),
    [details, reportType, summary, user?.email],
  );

  const copyReport = async () => {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    toast({ title: "Report copied", description: "Paste it into your support message so we have the full context." });
  };

  const sendReport = async () => {
    if (!summary.trim()) {
      toast({ variant: "destructive", title: "Add a short summary first" });
      return;
    }

    if (!supportEmail) {
      await copyReport();
      return;
    }

    const subject = encodeURIComponent(`[${reportType}] ${summary.trim()}`);
    const body = encodeURIComponent(report);
    window.location.assign(`mailto:${supportEmail}?subject=${subject}&body=${body}`);
  };

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8 px-5 py-8 pb-28 sm:px-8 lg:px-10 lg:py-12">
      <section className="relative overflow-hidden rounded-[2rem] border border-cfb-brand/30 bg-[linear-gradient(125deg,rgba(10,38,74,0.96),rgba(24,23,68,0.94))] p-7 shadow-[0_24px_70px_rgba(2,6,23,0.38)] sm:p-10">
        <div aria-hidden="true" className="absolute -right-16 -top-20 h-72 w-72 rounded-full bg-cfb-brand/15 blur-3xl" />
        <div className="relative max-w-2xl">
          <div className="mb-5 inline-flex items-center gap-3 rounded-full border border-cfb-brand/35 bg-slate-950/35 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-sky-100">
            <Bug className="h-4 w-4 text-cfb-brand" />
            Beta feedback
          </div>
          <h1 className="font-display text-4xl font-black uppercase italic tracking-[-0.045em] text-white sm:text-5xl">Report a bug</h1>
          <p className="mt-4 text-base leading-7 text-slate-200/80 sm:text-lg">
            Send the exact behavior you saw. Include the affected player, league, or screen when relevant so the team can reproduce it.
          </p>
        </div>
      </section>

      <section className="rounded-[2rem] border border-cfb-border-subtle bg-slate-950/55 p-6 shadow-[0_18px_55px_rgba(2,6,23,0.32)] sm:p-8">
        <div className="mb-7 flex items-start gap-3 rounded-2xl border border-sky-300/20 bg-sky-300/10 px-4 py-3 text-sm leading-6 text-sky-50/90">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-sky-200" />
          Do not include passwords, access codes, or private league invite codes in a report.
        </div>

        <div className="grid gap-6 sm:grid-cols-[minmax(0,1fr)_180px]">
          <div className="space-y-2">
            <Label htmlFor="bug-summary" className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-300">What happened?</Label>
            <Input id="bug-summary" value={summary} onChange={(event) => setSummary(event.target.value)} placeholder="Short description of the issue" maxLength={160} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bug-type" className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-300">Report type</Label>
            <select id="bug-type" value={reportType} onChange={(event) => setReportType(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring">
              {REPORT_TYPES.map((type) => <option key={type}>{type}</option>)}
            </select>
          </div>
        </div>

        <div className="mt-6 space-y-2">
          <Label htmlFor="bug-details" className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-300">Steps and details</Label>
          <Textarea id="bug-details" value={details} onChange={(event) => setDetails(event.target.value)} placeholder="What did you click? What did you expect to happen? What happened instead?" className="min-h-40 resize-y" />
        </div>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={() => void copyReport()} className="gap-2">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Report copied" : "Copy report"}
          </Button>
          <Button type="button" onClick={() => void sendReport()} className="gap-2">
            <Mail className="h-4 w-4" />
            {supportEmail ? "Email report" : "Copy report to send"}
          </Button>
        </div>
      </section>
    </main>
  );
}
