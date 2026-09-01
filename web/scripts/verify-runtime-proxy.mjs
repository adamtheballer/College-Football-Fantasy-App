const webBase = (process.env.WEB_RUNTIME_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const directApiBase = process.env.DIRECT_API_RUNTIME_URL?.replace(/\/$/, "");

const readExpectedBoolean = (name) => {
  const value = process.env[name];
  if (value === undefined || value === "") return undefined;
  if (value === "true") return true;
  if (value === "false") return false;
  throw new Error(`${name} must be true or false when provided.`);
};

const requireJson = (response, label) => {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`${label} returned ${contentType || "no Content-Type"}, not JSON.`);
  }
};

const fetchJson = async (path, label, acceptedStatuses = [200]) => {
  const response = await fetch(`${webBase}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!acceptedStatuses.includes(response.status)) {
    throw new Error(`${label} failed: ${path} returned ${response.status}.`);
  }
  requireJson(response, label);
  return response.json();
};

const health = await fetchJson("/api/health", "Browser API health channel");
if (health?.status !== "ok") {
  throw new Error(`Browser API health channel returned an unexpected payload: ${JSON.stringify(health)}.`);
}

const payload = await fetchJson("/api/health/ready", "Browser API readiness channel");
if (payload?.status !== "ready") {
  throw new Error(`Browser API channel is not ready: ${JSON.stringify(payload)}.`);
}

const identity = await fetchJson("/api/health/runtime", "Browser API runtime channel");
const players = await fetchJson("/api/players?limit=1&offset=0", "Browser player-list channel");
if (!Array.isArray(players?.data)) {
  throw new Error("Browser player-list channel did not return a data array.");
}
const playerId = players.data[0]?.id;
if (!Number.isInteger(playerId)) {
  throw new Error("Browser player-list channel returned no player ID for schedule validation.");
}

const projections = await fetchJson(
  "/api/projections?season=2026&week=1&limit=1&offset=0",
  "Browser projection channel",
);
if (!Array.isArray(projections?.data)) {
  throw new Error("Browser projection channel did not return a data array.");
}
await fetchJson(
  `/api/schedule/player/${playerId}?season=2026&week=1&weeks=1`,
  "Browser schedule channel",
);
await fetchJson("/api/auth/me", "Browser unauthenticated auth channel", [200, 401, 403]);
await fetchJson(
  "/api/saturday-pick-6/current?season=2026&week=1",
  "Browser Saturday Pick 6 channel",
  [200, 401, 403, 404],
);

const runtimeResponse = await fetch(`${webBase}/api/health/runtime`, {
  headers: { Accept: "application/json" },
});
const responseRevision = runtimeResponse.headers.get("x-cff-revision");
if (!identity?.api_process_instance_uuid || !identity?.database_instance_uuid || !identity?.git_sha) {
  throw new Error(`Runtime identity is incomplete: ${JSON.stringify(identity)}.`);
}
if (responseRevision && responseRevision !== identity.git_sha) {
  throw new Error(`Proxy revision mismatch: header=${responseRevision} body=${identity.git_sha}.`);
}

const expectedRevision = process.env.CFF_GIT_SHA;
if (expectedRevision && expectedRevision !== "unknown" && identity.git_sha !== expectedRevision) {
  throw new Error(`Unexpected API revision: expected=${expectedRevision} actual=${identity.git_sha}.`);
}
const expectedScoringMode = process.env.CFF_EXPECT_SCORING_MODE;
const expectedSportsdataEnabled = readExpectedBoolean("CFF_EXPECT_SPORTSDATA_ENABLED");
const expectedProviderPolling = readExpectedBoolean("CFF_EXPECT_PROVIDER_POLLING_EXPECTED");
if (expectedScoringMode && identity.scoring_mode !== expectedScoringMode) {
  throw new Error(`Unexpected scoring mode: expected=${expectedScoringMode} actual=${identity.scoring_mode}.`);
}
if (expectedSportsdataEnabled !== undefined && identity.sportsdata_enabled !== expectedSportsdataEnabled) {
  throw new Error(`Unexpected SportsData policy: expected=${expectedSportsdataEnabled} actual=${identity.sportsdata_enabled}.`);
}
if (expectedProviderPolling !== undefined && identity.provider_polling_expected !== expectedProviderPolling) {
  throw new Error(`Unexpected provider polling policy: expected=${expectedProviderPolling} actual=${identity.provider_polling_expected}.`);
}

if (directApiBase) {
  const directResponse = await fetch(`${directApiBase}/health/runtime`, {
    headers: { Accept: "application/json" },
  });
  if (!directResponse.ok) {
    throw new Error(`Direct Railway runtime channel failed: ${directApiBase}/health/runtime returned ${directResponse.status}.`);
  }
  requireJson(directResponse, "Direct Railway runtime channel");
  const direct = await directResponse.json();
  for (const key of ["git_sha", "database_instance_uuid", "alembic_revision", "runtime_mode", "readiness_status"]) {
    if (identity[key] !== direct[key]) {
      throw new Error(`Vercel/Railway runtime skew for ${key}: proxied=${identity[key]} direct=${direct[key]}.`);
    }
  }
}

console.log(`Runtime verified: ${webBase} is serving JSON through same-origin /api for ${identity.git_sha}.`);
