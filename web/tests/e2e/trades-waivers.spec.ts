import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const e2eDir = path.dirname(fileURLToPath(import.meta.url));

const readCoreWorkflowSpec = () => readFileSync(path.join(e2eDir, "core-workflows.spec.ts"), "utf8");

test.describe("trades and waivers e2e coverage contract", () => {
  test("browser suite covers honest trade and available-player workflows", async () => {
    const source = readCoreWorkflowSpec();

    expect(source).toContain("trade builder analyzes selected players but remains preview-only");
    expect(source).toContain("available players page marks claims disabled and avoids add-drop");
    expect(source).toContain("Claims are not enabled yet");
    expect(source).toContain("Watchlist");
  });
});
