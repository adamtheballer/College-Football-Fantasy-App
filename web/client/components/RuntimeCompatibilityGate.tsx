import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";

import { buildApiUrl } from "@/lib/api";
import {
  publishRuntimeDebugIdentity,
  runtimeCompatibilityError,
  runtimeDeploymentSkew,
  type RuntimeIdentity,
  WEB_BUILD_SHA,
} from "@/lib/runtime-compatibility";

type GateState =
  | { status: "checking" }
  | { status: "ready" }
  | { status: "blocked"; reason: string; runtimeId: string };

export type RuntimeCapabilities = Pick<
  RuntimeIdentity,
  | "email_enabled"
  | "support_email"
  | "privacy_policy_url"
  | "terms_url"
  | "provider_disclosure_url"
>;

// Treat capabilities as disabled until the API explicitly supplies them. This
// prevents a failed runtime-config fetch from manufacturing a mail or legal link.
const disabledCapabilities: RuntimeCapabilities = { email_enabled: false };
const RuntimeCapabilitiesContext =
  createContext<RuntimeCapabilities>(disabledCapabilities);

export const useRuntimeCapabilities = () =>
  useContext(RuntimeCapabilitiesContext);

const RuntimeCompatibilityGate = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<GateState>({ status: "checking" });
  const [capabilities, setCapabilities] =
    useState<RuntimeCapabilities>(disabledCapabilities);

  useEffect(() => {
    let active = true;
    const verify = async () => {
      try {
        const response = await fetch(buildApiUrl("/health/runtime"), {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`runtime status ${response.status}`);
        const runtime = (await response.json()) as RuntimeIdentity;
        const hostname = window.location.hostname;
        const deploymentSkew = runtimeDeploymentSkew(runtime, { hostname });
        const reason = runtimeCompatibilityError(runtime, { hostname });
        if (!active) return;
        publishRuntimeDebugIdentity(runtime, deploymentSkew);
        setCapabilities({
          email_enabled: runtime.email_enabled === true,
          support_email: runtime.support_email || null,
          privacy_policy_url: runtime.privacy_policy_url || null,
          terms_url: runtime.terms_url || null,
          provider_disclosure_url: runtime.provider_disclosure_url || null,
        });
        setState(
          reason
            ? {
                status: "blocked",
                reason,
                runtimeId:
                  runtime.runtime_id ||
                  runtime.api_process_instance_uuid ||
                  "unavailable",
              }
            : { status: "ready" },
        );
      } catch {
        // Network availability is handled by normal API error states. Only a proven
        // incompatible runtime blocks the application shell.
        if (active) setState({ status: "ready" });
      }
    };
    void verify();
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-black uppercase tracking-[0.18em] text-sky-100">
        Verifying release runtime…
      </div>
    );
  }

  if (state.status === "blocked") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-center text-slate-100">
        <section className="max-w-xl rounded-3xl border border-rose-300/35 bg-slate-900/90 p-8 shadow-2xl">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-rose-300">
            Release protection
          </p>
          <h1 className="mt-3 text-3xl font-black uppercase italic">
            Application update mismatch
          </h1>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Refreshing the release runtime is required. {state.reason}
          </p>
          <p className="mt-6 text-xs font-mono text-slate-400">
            Web: {WEB_BUILD_SHA} · Runtime: {state.runtimeId}
          </p>
        </section>
      </main>
    );
  }

  return (
    <RuntimeCapabilitiesContext.Provider value={capabilities}>
      {children}
    </RuntimeCapabilitiesContext.Provider>
  );
};

export default RuntimeCompatibilityGate;
