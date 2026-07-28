import { useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";

import { apiGet } from "@/lib/api";
import { Button } from "@/components/ui/button";

type RuntimeDiagnostics = {
  status: string;
  environment: string;
  api_build_sha: string;
  database: string;
  migrations: string;
  expected_revisions: string[];
  current_revisions: string[];
  detail: string;
};

const webBuildSha = (import.meta.env.VITE_BUILD_SHA as string | undefined) || "unknown";

const displaySha = (sha: string) => (sha === "unknown" ? sha : sha.slice(0, 12));

export function RuntimeDiagnosticsPanel() {
  const [runtime, setRuntime] = useState<RuntimeDiagnostics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRuntime = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiGet<RuntimeDiagnostics>("/health/runtime");
      setRuntime(payload);
    } catch {
      setRuntime(null);
      setError("Runtime diagnostics are unavailable. Confirm the deployed web and API builds match.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRuntime();
  }, []);

  return (
    <section className="rounded-[2.5rem] border border-sky-300/20 bg-card/40 p-8 shadow-[0_20px_50px_rgba(0,0,0,0.3)] sm:p-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="rounded-2xl bg-sky-400/10 p-3 text-sky-200">
            <Activity className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-sky-200">Runtime Diagnostics</h2>
            <p className="mt-1 text-xs text-muted-foreground">Verify that the web app and API are on the intended release.</p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-xl text-[10px] font-black uppercase tracking-[0.16em]"
          onClick={() => void loadRuntime()}
          disabled={loading}
        >
          <RefreshCw className={loading ? "mr-2 h-3.5 w-3.5 animate-spin" : "mr-2 h-3.5 w-3.5"} />
          Refresh
        </Button>
      </div>

      {error ? <p role="alert" className="mt-6 text-sm font-semibold text-amber-200">{error}</p> : null}

      <dl className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-busy={loading}>
        <Diagnostic label="Web SHA" value={displaySha(webBuildSha)} />
        <Diagnostic label="API SHA" value={runtime ? displaySha(runtime.api_build_sha) : loading ? "Loading…" : "Unavailable"} />
        <Diagnostic
          label="Migration"
          value={runtime ? runtime.current_revisions.join(", ") || "Missing" : loading ? "Loading…" : "Unavailable"}
        />
        <Diagnostic label="Environment" value={runtime?.environment ?? (loading ? "Loading…" : "Unavailable")} />
      </dl>

      {runtime ? (
        <p className="mt-5 text-[11px] font-semibold text-muted-foreground">
          API status: <span className="text-foreground">{runtime.status}</span> · database: <span className="text-foreground">{runtime.database}</span> · migrations: <span className="text-foreground">{runtime.migrations}</span>
        </p>
      ) : null}
    </section>
  );
}

function Diagnostic({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/35 px-4 py-4">
      <dt className="text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground">{label}</dt>
      <dd className="mt-2 break-all font-mono text-xs font-bold text-foreground">{value}</dd>
    </div>
  );
}
