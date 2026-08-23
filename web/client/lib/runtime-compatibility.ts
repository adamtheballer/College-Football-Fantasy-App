export type RuntimeIdentity = {
  git_sha: string;
  git_branch: string;
  runtime_id?: string | null;
  runtime_mode: string;
  environment: string;
  api_process_instance_uuid: string;
  web_git_sha: string;
  worker_git_sha: string;
  database_instance_uuid?: string | null;
  alembic_revision?: string | null;
  readiness_status: string;
  scoring_mode: string;
  sportsdata_enabled: boolean;
  email_enabled: boolean;
  password_reset_enabled: boolean;
  password_reset_email_configured: boolean;
  support_email?: string | null;
  privacy_policy_url?: string | null;
  terms_url?: string | null;
  provider_disclosure_url?: string | null;
};

export const WEB_BUILD_SHA = import.meta.env.VITE_GIT_SHA || "unknown";

type CompatibilityOptions = {
  hostname?: string;
  frontendGitSha?: string;
};

export type RuntimeDebugIdentity = Pick<
  RuntimeIdentity,
  | "git_sha"
  | "git_branch"
  | "runtime_mode"
  | "environment"
  | "api_process_instance_uuid"
  | "web_git_sha"
  | "worker_git_sha"
  | "database_instance_uuid"
  | "alembic_revision"
  | "readiness_status"
  | "scoring_mode"
  | "sportsdata_enabled"
> & {
  frontend_git_sha: string;
  deployment_skew: string | null;
};

declare global {
  interface Window {
    __CFF_RUNTIME__?: Readonly<RuntimeDebugIdentity>;
  }
}

export const isVercelPreviewHostname = (hostname: string | undefined): boolean => {
  const normalized = hostname?.trim().toLowerCase() ?? "";
  return normalized.length > ".vercel.app".length && normalized.endsWith(".vercel.app");
};

export const runtimeDeploymentSkew = (
  runtime: RuntimeIdentity,
  { hostname, frontendGitSha = WEB_BUILD_SHA }: CompatibilityOptions = {}
): string | null => {
  if (frontendGitSha === "unknown" || frontendGitSha === runtime.git_sha) return null;
  return isVercelPreviewHostname(hostname)
    ? "A Vercel preview bundle is using an aligned runtime from a different release."
    : "The page bundle does not match the running API release.";
};

export const runtimeCompatibilityError = (
  runtime: RuntimeIdentity,
  { hostname, frontendGitSha = WEB_BUILD_SHA }: CompatibilityOptions = {}
): string | null => {
  const required = [runtime.git_sha, runtime.web_git_sha, runtime.worker_git_sha];
  if (required.some((value) => !value || value === "unknown")) {
    return "The release runtime did not provide complete build identity information.";
  }
  if (new Set(required).size !== 1) {
    return "The API, web, and worker build identities do not match.";
  }
  // A browser may retain the immediately previous, fully compatible bundle
  // while a CDN rollout promotes newer static assets. Blocking the shell in
  // that state cannot repair the cache and can strand installed iOS web apps.
  // Preserve the skew in the public diagnostic identity, but only block on a
  // proven server-side split release above.
  return null;
};

// This contains only the public runtime fields already returned by
// /health/runtime; it deliberately omits credentials, cookies, and URLs with
// secret material. The existing fail-closed release gate remains in place.
export const publishRuntimeDebugIdentity = (runtime: RuntimeIdentity, deploymentSkew: string | null) => {
  if (typeof window === "undefined") return;
  window.__CFF_RUNTIME__ = Object.freeze({
    git_sha: runtime.git_sha,
    git_branch: runtime.git_branch,
    runtime_mode: runtime.runtime_mode,
    environment: runtime.environment,
    api_process_instance_uuid: runtime.api_process_instance_uuid,
    web_git_sha: runtime.web_git_sha,
    worker_git_sha: runtime.worker_git_sha,
    database_instance_uuid: runtime.database_instance_uuid ?? null,
    alembic_revision: runtime.alembic_revision ?? null,
    readiness_status: runtime.readiness_status,
    scoring_mode: runtime.scoring_mode,
    sportsdata_enabled: runtime.sportsdata_enabled,
    frontend_git_sha: WEB_BUILD_SHA,
    deployment_skew: deploymentSkew,
  });
};
