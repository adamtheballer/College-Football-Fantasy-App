export type LegalDocumentKey = "privacy" | "terms" | "providerDisclosure";

export const INTERNAL_LEGAL_PATHS: Record<LegalDocumentKey, string> = {
  privacy: "/privacy",
  terms: "/terms",
  providerDisclosure: "/provider-disclosure",
};

/**
 * Runtime configuration may point to a canonical policy URL after deployment.
 * Until then, retain a working first-party route instead of hiding legal links.
 */
export const resolveLegalDocumentHref = (
  configuredUrl: string | null | undefined,
  documentKey: LegalDocumentKey,
): string => {
  const normalized = configuredUrl?.trim();
  return normalized || INTERNAL_LEGAL_PATHS[documentKey];
};

export const isExternalLegalHref = (href: string) => /^https?:\/\//i.test(href);
