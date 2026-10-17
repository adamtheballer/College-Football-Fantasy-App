export const CONFERENCE_OPTIONS = [
  { code: "SEC", label: "SEC", detail: "16 schools" },
  { code: "BIG10", label: "Big Ten", detail: "18 schools" },
  { code: "BIG12", label: "Big 12", detail: "16 schools" },
  { code: "ACC", label: "ACC", detail: "17 schools" },
  { code: "INDEPENDENT", label: "Independent", detail: "Notre Dame" },
] as const;
export type ConferenceCode = (typeof CONFERENCE_OPTIONS)[number]["code"];
export const DEFAULT_CONFERENCE_CODES: ConferenceCode[] = CONFERENCE_OPTIONS.map(option => option.code);

/** Canonicalize local mock settings; pre-selection saved mocks retain the full pool. */
export function mockConferenceCodes(value: unknown): ConferenceCode[] {
  if (!Array.isArray(value)) return [...DEFAULT_CONFERENCE_CODES];
  const selected = new Set(value.filter((code): code is string => typeof code === "string").map(code => code.trim().toUpperCase()));
  const codes = DEFAULT_CONFERENCE_CODES.filter(code => selected.has(code));
  return codes.length ? codes : [...DEFAULT_CONFERENCE_CODES];
}
export function conferencePoolLabel(codes: readonly ConferenceCode[]) {
  return CONFERENCE_OPTIONS.filter(option => codes.includes(option.code)).map(option => option.label).join(" + ");
}
