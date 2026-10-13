import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const globalCss = readFileSync(fileURLToPath(new URL("./global.css", import.meta.url)), "utf8");
const tailwindConfig = readFileSync(fileURLToPath(new URL("../tailwind.config.ts", import.meta.url)), "utf8");

describe("college football typography system", () => {
  it("self-hosts rounded body and athletic display fonts", () => {
    expect(globalCss).toContain('@import "@fontsource/poppins/latin-400.css"');
    expect(globalCss).toContain('@import "@fontsource/exo-2/latin-800-italic.css"');
    expect(globalCss).not.toContain("fonts.googleapis.com");
  });

  it("uses Poppins for operational UI and quotes the numeric Exo 2 font name", () => {
    expect(tailwindConfig).toMatch(/sans:\s*\[\s*"Poppins"/);
    expect(tailwindConfig).toMatch(/ui:\s*\[\s*"Poppins"/);
    // A numeric family name is invalid CSS unless quoted; browsers otherwise
    // silently discard it and render every heading in the body font.
    expect(tailwindConfig).toMatch(/display:\s*\[\s*'"Exo 2"'/);
  });

  it("provides semantic text utilities and preserves mobile input readability", () => {
    for (const className of ["cfb-body", "cfb-ui-text", "cfb-display-title", "cfb-section-title", "cfb-micro-label", "cfb-stat-value", "cfb-button-label"]) {
      expect(globalCss).toContain(`.${className}`);
    }
    expect(globalCss).toContain("tabular-nums");
    expect(globalCss).toContain("font-size: 16px !important");
  });
});
