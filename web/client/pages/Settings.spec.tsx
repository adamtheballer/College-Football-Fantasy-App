// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  setActiveLeagueId: vi.fn(),
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
  useRuntimeCapabilities: () => ({}),
}));

vi.mock("@/components/auth/PasswordChangeForm", () => ({
  PasswordChangeForm: () => <div>Password form</div>,
}));

vi.mock("@/components/support/SupportContactCard", () => ({
  SupportContactCard: () => <div>Support</div>,
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

  it("saves and removes a manager profile image URL through the same profile update", async () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Profile image URL (optional)"), { target: { value: "https://images.example.com/adam.jpg" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(state.updateProfile).toHaveBeenCalledWith({ firstName: "Adam", avatarUrl: "https://images.example.com/adam.jpg" }));

    fireEvent.click(screen.getByRole("button", { name: /remove picture/i }));
    expect((screen.getByLabelText("Profile image URL (optional)") as HTMLInputElement).value).toBe("");
  });

  it("records an explicit replay request before returning to Home", () => {
    render(<MemoryRouter initialEntries={["/settings"]}><Settings /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: /start guide again/i }));

    expect(localStorage.getItem("cfb_pending_guide_7")).toBe("true");
  });
});
