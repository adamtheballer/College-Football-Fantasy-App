// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  isVercelPreviewHostname,
  publishRuntimeDebugIdentity,
  runtimeCompatibilityError,
  runtimeDeploymentSkew,
  type RuntimeIdentity,
} from "./runtime-compatibility";

const runtime = (overrides: Partial<RuntimeIdentity> = {}): RuntimeIdentity => ({
  git_sha: "release-sha",
  git_branch: "main",
  runtime_id: "beta-release-sha",
  runtime_mode: "beta",
  environment: "production",
  api_process_instance_uuid: "api-instance",
  web_git_sha: "release-sha",
  worker_git_sha: "release-sha",
  database_instance_uuid: "database-instance",
  alembic_revision: "0089_trade_private_chat",
  readiness_status: "ready",
  scoring_mode: "disabled",
  sportsdata_enabled: false,
  email_enabled: false,
  ...overrides,
});

describe("publishRuntimeDebugIdentity", () => {
  it("publishes only non-secret deployment provenance for operator inspection", () => {
    publishRuntimeDebugIdentity(runtime(), null);

    expect(window.__CFF_RUNTIME__).toMatchObject({
      frontend_git_sha: expect.any(String),
      git_sha: "release-sha",
      database_instance_uuid: "database-instance",
      alembic_revision: "0089_trade_private_chat",
      deployment_skew: null,
    });
    expect(JSON.stringify(window.__CFF_RUNTIME__)).not.toContain("secret");
  });
});

describe("runtime compatibility", () => {
  it("allows only generated Vercel preview hosts to tolerate a frontend bundle skew", () => {
    expect(isVercelPreviewHostname("college-football-app-git-pr-37.vercel.app")).toBe(true);
    expect(isVercelPreviewHostname("vercel.app")).toBe(false);
    expect(isVercelPreviewHostname("www.collegefantasyfootball.org")).toBe(false);

    expect(
      runtimeCompatibilityError(runtime(), {
        hostname: "college-football-app-git-pr-37.vercel.app",
        frontendGitSha: "preview-sha",
      })
    ).toBeNull();
    expect(
      runtimeDeploymentSkew(runtime(), {
        hostname: "college-football-app-git-pr-37.vercel.app",
        frontendGitSha: "preview-sha",
      })
    ).toMatch(/Vercel preview bundle/i);
  });

  it("keeps a cached production bundle usable while reporting its deployment skew", () => {
    expect(
      runtimeCompatibilityError(runtime(), {
        hostname: "www.collegefantasyfootball.org",
        frontendGitSha: "preview-sha",
      })
    ).toBeNull();
    expect(
      runtimeDeploymentSkew(runtime(), {
        hostname: "www.collegefantasyfootball.org",
        frontendGitSha: "preview-sha",
      })
    ).toMatch(/page bundle does not match/i);
  });

  it("never waives API, web-runtime, or worker identity mismatches in previews", () => {
    expect(
      runtimeCompatibilityError(runtime({ worker_git_sha: "different-worker" }), {
        hostname: "college-football-app-git-pr-37.vercel.app",
        frontendGitSha: "preview-sha",
      })
    ).toMatch(/API, web, and worker build identities do not match/i);
  });
});
