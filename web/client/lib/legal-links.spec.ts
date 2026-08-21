import { describe, expect, it } from "vitest";

import { isExternalLegalHref, resolveLegalDocumentHref } from "./legal-links";

describe("legal document links", () => {
  it("uses the configured runtime URL when one is present", () => {
    expect(resolveLegalDocumentHref("https://collegefantasyfootball.org/privacy", "privacy")).toBe(
      "https://collegefantasyfootball.org/privacy",
    );
  });

  it("falls back to first-party public routes when runtime URLs are absent", () => {
    expect(resolveLegalDocumentHref(null, "privacy")).toBe("/privacy");
    expect(resolveLegalDocumentHref(undefined, "terms")).toBe("/terms");
    expect(resolveLegalDocumentHref("   ", "providerDisclosure")).toBe("/provider-disclosure");
  });

  it("opens only configured web URLs as external destinations", () => {
    expect(isExternalLegalHref("https://collegefantasyfootball.org/privacy")).toBe(true);
    expect(isExternalLegalHref("/privacy")).toBe(false);
  });
});
