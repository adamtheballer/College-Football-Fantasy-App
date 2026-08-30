import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const globalCss = readFileSync(fileURLToPath(new URL("./global.css", import.meta.url)), "utf8");
const tailwindConfig = readFileSync(fileURLToPath(new URL("../tailwind.config.ts", import.meta.url)), "utf8");

describe("college football typography system", () => {
  it("loads Josefin Sans with swap behavior", () => {
    expect(globalCss).toContain("family=Josefin+Sans:");
    expect(globalCss).toContain("display=swap");
    expect(globalCss).not.toContain("family=Barlow");
  });

  it("uses Josefin Sans for every body, operational UI, and display token", () => {
    expect(tailwindConfig).toMatch(/sans:\s*\[\s*"Josefin Sans"/);
    expect(tailwindConfig).toMatch(/ui:\s*\[\s*"Josefin Sans"/);
    expect(tailwindConfig).toMatch(/display:\s*\[\s*"Josefin Sans"/);
    expect(tailwindConfig).not.toContain('"Barlow');
  });

  it("provides semantic text utilities and preserves mobile input readability", () => {
    for (const className of ["cfb-body", "cfb-ui-text", "cfb-display-title", "cfb-section-title", "cfb-micro-label", "cfb-stat-value", "cfb-button-label"]) {
      expect(globalCss).toContain(`.${className}`);
    }
    expect(globalCss).toContain("tabular-nums");
    expect(globalCss).toContain("font-size: 16px !important");
  });
});
