// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import PrivacyPolicy from "./PrivacyPolicy";
import ProviderDisclosure from "./ProviderDisclosure";
import TermsOfUse from "./TermsOfUse";

const renderPublicDocument = (page: React.ReactElement) => render(<MemoryRouter>{page}</MemoryRouter>);

describe("public legal documents", () => {
  afterEach(cleanup);

  it("renders an identifiable privacy policy with the required information sections", () => {
    const { container } = renderPublicDocument(<PrivacyPolicy />);

    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Information We Collect" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "How We Use Information" })).toBeTruthy();
    expect(screen.getByText("Last updated: August 20, 2026")).toBeTruthy();
    expect(container.textContent).not.toMatch(/TODO|PLACEHOLDER|FIXME/i);
  });

  it("renders alpha-specific terms and projection guidance", () => {
    renderPublicDocument(<TermsOfUse />);

    expect(screen.getByRole("heading", { name: "Terms of Use" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Alpha Service" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Fantasy Projections" })).toBeTruthy();
  });

  it("renders the provider disclosure with live-scoring and projection sections", () => {
    renderPublicDocument(<ProviderDisclosure />);

    expect(screen.getByRole("heading", { name: "Provider & Data Disclosure" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Live Scoring" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Projections and Rankings" })).toBeTruthy();
    expect(screen.getByText(/not affiliated with or endorsed by ESPN/i)).toBeTruthy();
  });
});
