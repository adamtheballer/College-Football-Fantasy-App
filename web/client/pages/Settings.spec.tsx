// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  setActiveLeagueId: vi.fn(),
  prepareProfileImage: vi.fn(),
  runtimeCapabilities: {},
  user: { id: 7, firstName: "Adam", email: "adam@example.com", isAdmin: false, avatarUrl: null },
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    user: state.user,
    isBootstrapping: false,
    logoutAll: vi.fn(),
    updateProfile: state.updateProfile,
  }),
}));

vi.mock("@/hooks/use-leagues", () => ({
  useLeagues: () => ({ data: [{ id: 1, name: "Saturday League" }] }),
}));

vi.mock("@/hooks/use-active-league", () => ({
  useActiveLeagueId: () => ({ activeLeagueId: 1, setActiveLeagueId: state.setActiveLeagueId }),
}));

vi.mock("@/components/RuntimeCompatibilityGate", () => ({
  useRuntimeCapabilities: () => state.runtimeCapabilities,
}));

vi.mock("@/components/auth/PasswordChangeForm", () => ({
  PasswordChangeForm: () => <div>Password form</div>,
}));

vi.mock("@/components/support/SupportContactCard", () => ({
  SupportContactCard: () => <div>Support</div>,
}));

vi.mock("@/lib/profileImage", () => ({
  prepareProfileImage: state.prepareProfileImage,
}));

vi.mock("@/components/ui/select", async () => {
  const React = await import("react");
  const Context = React.createContext<{ onValueChange?: (value: string) => void }>({});
  return {
    Select: ({ onValueChange, children }: { onValueChange?: (value: string) => void; children: React.ReactNode }) => (
      <Context.Provider value={{ onValueChange }}>{children}</Context.Provider>
    ),
    SelectTrigger: ({ children, className }: { children: React.ReactNode; className?: string }) => <div className={className}>{children}</div>,
    SelectValue: ({ placeholder }: { placeholder?: string }) => <span>{placeholder}</span>,
    SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => {
      const { onValueChange } = React.useContext(Context);
      return <button type="button" onClick={() => onValueChange?.(value)}>{children}</button>;
    },
  };
});

import Settings from "./Settings";

describe("Settings beta preferences", () => {
  afterEach(cleanup);

  beforeEach(() => {
    localStorage.clear();
    state.updateProfile.mockReset();
    state.updateProfile.mockResolvedValue({ id: 7, firstName: "Updated Adam", avatarUrl: null });
    state.prepareProfileImage.mockReset();
    state.runtimeCapabilities = {};
  });

  it("shows the notification permission state without third-party theme controls", () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);

    expect(screen.getByText("App Preferences")).toBeTruthy();
    expect(screen.getByText("Notifications")).toBeTruthy();
    expect(screen.getByText("Push notifications")).toBeTruthy();
    expect(screen.getByText("Push notifications are not configured for this environment yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /enable push notifications/i }).getAttribute("disabled")).not.toBeNull();
    expect(screen.queryByText(/espn/i)).toBeNull();
  });

  it("saves the manager name through the self-only profile update flow", async () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Manager Name"), { target: { value: "Updated Adam" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(state.updateProfile).toHaveBeenCalledWith({ firstName: "Updated Adam", avatarUrl: null }));
  });

  it("keeps the image-address fallback available and removes it immediately", async () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Profile image URL (optional)"), { target: { value: "https://images.example.com/adam.jpg" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(state.updateProfile).toHaveBeenCalledWith({ firstName: "Adam", avatarUrl: "https://images.example.com/adam.jpg" }));

    fireEvent.click(screen.getByRole("button", { name: /remove picture/i }));
    await waitFor(() => expect(state.updateProfile).toHaveBeenLastCalledWith({ avatarUrl: null }));
  });

  it("shows a chosen mobile photo for review and updates the visible avatar as soon as Confirm Photo is clicked", async () => {
    const photoDataUrl = "data:image/jpeg;base64,/9j/4AAQ";
    state.prepareProfileImage.mockResolvedValue(photoDataUrl);
    let resolveProfileUpdate: (value: { id: number; firstName: string; avatarUrl: string }) => void;
    state.updateProfile.mockReturnValue(new Promise((resolve) => {
      resolveProfileUpdate = resolve;
    }));
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Choose a profile photo"), {
      target: { files: [new File(["photo"], "manager.png", { type: "image/png" })] },
    });

    await screen.findByRole("button", { name: /confirm photo/i });
    expect(state.updateProfile).not.toHaveBeenCalled();
    expect(screen.getByText(/manager\.png is ready/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /confirm photo/i }));
    await waitFor(() => expect(state.updateProfile).toHaveBeenCalledWith({ avatarUrl: "data:image/jpeg;base64,/9j/4AAQ" }));
    expect(screen.queryByRole("button", { name: /select photo/i })).toBeNull();
    expect(screen.getByAltText("Adam profile picture").getAttribute("src")).toBe(photoDataUrl);

    resolveProfileUpdate!({ id: 7, firstName: "Adam", avatarUrl: photoDataUrl });
  });

  it("records an explicit replay request before returning to Home", () => {
    render(<MemoryRouter initialEntries={["/settings"]}><Settings /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: /start guide again/i }));

    expect(localStorage.getItem("cfb_pending_guide_7")).toBe("true");
  });

  it("keeps policy links available with internal fallbacks until runtime URLs are configured", () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);

    expect(screen.getByRole("link", { name: "Privacy Policy" }).getAttribute("href")).toBe("/privacy");
    expect(screen.getByRole("link", { name: "Terms" }).getAttribute("href")).toBe("/terms");
    expect(screen.getByRole("link", { name: "Provider Disclosure" }).getAttribute("href")).toBe("/provider-disclosure");
  });

  it("uses a configured runtime policy URL when available", () => {
    state.runtimeCapabilities = { privacy_policy_url: "https://collegefantasyfootball.org/privacy" };
    render(<MemoryRouter><Settings /></MemoryRouter>);

    const privacyLink = screen.getByRole("link", { name: "Privacy Policy" });
    expect(privacyLink.getAttribute("href")).toBe("https://collegefantasyfootball.org/privacy");
    expect(privacyLink.getAttribute("target")).toBe("_blank");
  });
});
