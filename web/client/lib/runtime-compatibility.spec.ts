// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  publishRuntimeDebugIdentity,
  type RuntimeIdentity,
} from "./runtime-compatibility";

const runtime: RuntimeIdentity = {
  git_sha: "api-sha",
  git_branch: "main",
  runtime_mode: "production",
  environment: "production",
  api_process_instance_uuid: "api-instance",
  web_git_sha: "api-sha",
  worker_git_sha: "api-sha",
  database_instance_uuid: "database-instance",
  alembic_revision: "0088_beta_scoring_lock",
  readiness_status: "ready",
  scoring_mode: "disabled",
  sportsdata_enabled: false,
  email_enabled: false,
};

describe("publishRuntimeDebugIdentity", () => {
  it("publishes only non-secret deployment provenance for operator inspection", () => {
    publishRuntimeDebugIdentity(runtime, null);

    expect(window.__CFF_RUNTIME__).toMatchObject({
      frontend_git_sha: expect.any(String),
      git_sha: "api-sha",
      database_instance_uuid: "database-instance",
      alembic_revision: "0088_beta_scoring_lock",
      deployment_skew: null,
    });
    expect(JSON.stringify(window.__CFF_RUNTIME__)).not.toContain("secret");
  });
});
