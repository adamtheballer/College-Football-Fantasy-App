import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const e2eDir = path.dirname(fileURLToPath(import.meta.url));

const readCoreWorkflowSpec = () => readFileSync(path.join(e2eDir, "core-workflows.spec.ts"), "utf8");

test.describe("draft e2e coverage contract", () => {
  test("browser suite covers real draft and mock draft flows", async () => {
    const source = readCoreWorkflowSpec();

    expect(source).toContain("draft-room pick mutation updates persisted draft state in UI");
    expect(source).toContain("single-player mock draft stays local and resets without real roster mutation");
  });
});
