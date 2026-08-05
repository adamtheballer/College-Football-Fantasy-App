const webBase = (process.env.WEB_RUNTIME_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");

const response = await fetch(`${webBase}/api/health/ready`, {
  headers: { Accept: "application/json" },
});

if (!response.ok) {
  throw new Error(`Browser API channel failed: ${webBase}/api/health/ready returned ${response.status}.`);
}

const payload = await response.json();
if (payload?.status !== "ready") {
  throw new Error(`Browser API channel is not ready: ${JSON.stringify(payload)}.`);
}

const identityResponse = await fetch(`${webBase}/api/health/identity`, {
  headers: { Accept: "application/json" },
});
if (!identityResponse.ok) {
  throw new Error(`Browser API identity channel failed: ${webBase}/api/health/identity returned ${identityResponse.status}.`);
}

const identity = await identityResponse.json();
const responseRevision = identityResponse.headers.get("x-cff-revision");
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
if (identity.scoring_mode !== "disabled" || identity.sportsdata_enabled !== false || identity.provider_polling_expected !== false) {
  throw new Error(`Beta provider policy is not disabled: ${JSON.stringify(identity)}.`);
}

console.log(`Runtime verified: ${webBase} is serving the UI and its same-origin /api channel is ready for ${identity.git_sha}.`);
