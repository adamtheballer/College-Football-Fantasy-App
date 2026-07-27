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

console.log(`Runtime verified: ${webBase} is serving the UI and its same-origin /api channel is ready.`);
