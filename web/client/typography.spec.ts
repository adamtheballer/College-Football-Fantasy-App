import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const globalCss = readFileSync(fileURLToPath(new URL("./global.css", import.meta.url)), "utf8");
const tailwindConfig = readFileSync(fileURLToPath(new URL("../tailwind.config.ts", import.meta.url)), "utf8");

describe("college football typography system", () => {
  it("loads only the approved Barlow families with swap behavior", () => {
    expect(globalCss).toContain("family=Barlow:");
    expect(globalCss).toContain("family=Barlow+Semi+Condensed:");
    expect(globalCss).toContain("family=Barlow+Condensed:");
    expect(globalCss).toContain("display=swap");
    expect(globalCss).not.toContain("family=Inter");
  });

  it("keeps body, operational UI, and display typography as distinct Tailwind tokens", () => {
    expect(tailwindConfig).toMatch(/sans:\s*\[\s*"Barlow"/);
    expect(tailwindConfig).toMatch(/ui:\s*\[\s*"Barlow Semi Condensed"/);
    expect(tailwindConfig).toMatch(/display:\s*\[\s*"Barlow Condensed"/);
    expect(tailwindConfig).not.toContain('"Inter"');
  });

  it("provides semantic text utilities and preserves mobile input readability", () => {
    for (const className of ["cfb-body", "cfb-ui-text", "cfb-display-title", "cfb-section-title", "cfb-micro-label", "cfb-stat-value", "cfb-button-label"]) {
      expect(globalCss).toContain(`.${className}`);
    }
    expect(globalCss).toContain("tabular-nums");
    expect(globalCss).toContain("font-size: 16px !important");
  });
});
