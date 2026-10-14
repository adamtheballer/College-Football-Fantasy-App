// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./use-auth";

vi.mock("@/lib/push-notifications", () => ({ clearBrowserPushIdentity: vi.fn(), syncBrowserPushIdentity: vi.fn() }));
const originalFetch = globalThis.fetch;
const payload = { id: 7, first_name: "Old Manager", email: "manager@example.com", avatar_url: null };
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
const deferred = () => { let resolve!: (response: Response) => void; const promise = new Promise<Response>((done) => { resolve = done; }); return { promise, resolve }; };
let auth: ReturnType<typeof useAuth>;
function Probe() { auth = useAuth(); return <output>{`${auth.isBootstrapping}:${auth.user?.id}:${auth.user?.firstName}`}</output>; }
const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>);
beforeEach(() => {
  localStorage.setItem("cfb_user", JSON.stringify({ id: 7, firstName: "Old Manager", email: payload.email, isAdmin: false, avatarUrl: null }));
  localStorage.setItem("cfb_access_token", "local-test-token"); localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
});
afterEach(() => { cleanup(); localStorage.clear(); globalThis.fetch = originalFetch; vi.restoreAllMocks(); });

describe("authoritative profile cache updates", () => {
  it("sends ownership precondition, caches confirmed name and retains it after remount", async () => {
    let name = "Old Manager";
    globalThis.fetch = vi.fn(async (_, options) => {
      if (options?.method === "PATCH") name = JSON.parse(options.body as string).first_name;
      return json({ ...payload, first_name: name });
    });
    const view = mount(); await waitFor(() => expect(screen.getByText("false:7:Old Manager")).toBeTruthy());
    await act(async () => auth.updateProfile({ firstName: "Saved Manager" }));
    expect(screen.getByText("false:7:Saved Manager")).toBeTruthy();
    const patch = vi.mocked(fetch).mock.calls.find((call) => call[1]?.method === "PATCH")!;
    expect(patch[1]?.headers).toMatchObject({ "X-CFFB-Profile-Account": "7" });
    expect(JSON.parse(patch[1]?.body as string)).toEqual({ first_name: "Saved Manager" });
    view.unmount(); mount(); await waitFor(() => expect(screen.getByText("false:7:Saved Manager")).toBeTruthy());
  });
  it("a late bootstrap profile cannot overwrite the newer saved name", async () => {
    const oldRead = deferred(); globalThis.fetch = vi.fn().mockReturnValueOnce(oldRead.promise).mockResolvedValue(json({ ...payload, first_name: "Saved Manager" }));
    mount(); await waitFor(() => expect(auth.user?.id).toBe(7));
    await act(async () => auth.updateProfile({ firstName: "Saved Manager" }));
    await act(async () => oldRead.resolve(json(payload)));
    expect(auth.user?.firstName).toBe("Saved Manager");
    expect(JSON.parse(localStorage.getItem("cfb_user")!).firstName).toBe("Saved Manager");
  });
  it("a stale account save cannot overwrite a switched account", async () => {
    const pending = deferred(); globalThis.fetch = vi.fn().mockResolvedValueOnce(json(payload)).mockReturnValueOnce(pending.promise);
    mount(); await waitFor(() => expect(auth.isBootstrapping).toBe(false));
    const save = auth.updateProfile({ firstName: "Late Name" }); const rejected = expect(save).rejects.toMatchObject({ status: 409 });
    await act(async () => {
      localStorage.setItem("cfb_user", JSON.stringify({ id: 22, firstName: "Second Account", email: "second@example.com", isAdmin: false, avatarUrl: null }));
      window.dispatchEvent(new Event("storage")); pending.resolve(json({ ...payload, first_name: "Late Name" }));
      await rejected;
    });
    expect(auth.user?.id).toBe(22); expect(auth.user?.firstName).toBe("Second Account");
  });
  it("older overlapping response cannot replace a newer confirmed save", async () => {
    const oldSave = deferred(); globalThis.fetch = vi.fn().mockResolvedValueOnce(json(payload)).mockReturnValueOnce(oldSave.promise).mockResolvedValueOnce(json({ ...payload, first_name: "Newest Manager" }));
    mount(); await waitFor(() => expect(auth.isBootstrapping).toBe(false));
    const old = auth.updateProfile({ firstName: "Old Response" }); const rejected = expect(old).rejects.toMatchObject({ status: 409 });
    await act(async () => auth.updateProfile({ firstName: "Newest Manager" }));
    await act(async () => { oldSave.resolve(json({ ...payload, first_name: "Old Response" })); await rejected; });
    expect(auth.user?.firstName).toBe("Newest Manager");
  });
  it("network/storage errors do not update profile caches", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce(json(payload)).mockRejectedValueOnce(new Error("offline"));
    mount(); await waitFor(() => expect(auth.isBootstrapping).toBe(false));
    await expect(auth.updateProfile({ firstName: "Not Saved" })).rejects.toMatchObject({ status: 0 });
    expect(auth.user?.firstName).toBe("Old Manager");
  });
});
