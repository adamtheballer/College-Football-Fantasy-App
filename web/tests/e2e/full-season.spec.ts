import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const e2eDir = path.dirname(fileURLToPath(import.meta.url));

const readCoreWorkflowSpec = () => readFileSync(path.join(e2eDir, "core-workflows.spec.ts"), "utf8");

test.describe("full-season e2e coverage contract", () => {
  test("core workflow spec covers the publication-critical fantasy lifecycle", async () => {
    const source = readCoreWorkflowSpec();

    expect(source).toContain("login flow stores auth session");
    expect(source).toContain("create league workflow posts to backend and opens league hub");
    expect(source).toContain("join-by-code flow previews league and joins with backend response");
    expect(source).toContain("available players");
    expect(source).toContain("draft-room pick mutation");
    expect(source).toContain("league matchup page renders projected teams and honest empty state");
    expect(source).toContain("trade builder");
    expect(source).toContain("watchlist create/add/remove persists through backend contracts");
  });
});
