// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
const mock = vi.hoisted(() => ({ auth: { user: null as null | { id: number }, isBootstrapping: true }, get: vi.fn(), native:false, listener:vi.fn(), remove:vi.fn() }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => mock.auth }));
vi.mock("@/hooks/use-notifications", () => ({ useNotifications: () => ({ data: null }) }));
vi.mock("@/lib/api", () => ({ apiGet: mock.get }));
vi.mock("@/lib/push-notifications", () => ({ clearBrowserPushIdentity: vi.fn(), syncBrowserPushIdentity: vi.fn(), updatePhoneNotificationBadge: vi.fn().mockResolvedValue(undefined) }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => mock.native } }));
vi.mock("@capacitor/app", () => ({App:{addListener:mock.listener}}));
import { focusManager } from "@tanstack/react-query";
import { PushNotificationCoordinator } from "./PushNotificationCoordinator";
import { clearPendingPushTap, queuePushTap, readPendingPushTap } from "@/lib/push-navigation";
const Location = () => { const location = useLocation(); return <output>{location.pathname}{location.search}</output>; };
const UI = () => <MemoryRouter><PushNotificationCoordinator /><Location /></MemoryRouter>;
beforeEach(() => { mock.native=false; mock.listener.mockReset();mock.remove.mockReset();mock.listener.mockResolvedValue({remove:mock.remove}); mock.auth = { user: null, isBootstrapping: true }; mock.get.mockReset(); clearPendingPushTap(); });
afterEach(()=>{cleanup();focusManager.setFocused(undefined);});
it("waits through session restoration and login before opening the server-approved league/week", async () => {
  queuePushTap({ event_id: 3, recipient_user_id: 7, url: "https://evil.test" });
  const view = render(<UI />); expect(mock.get).not.toHaveBeenCalled();
  mock.auth = { user: null, isBootstrapping: false }; view.rerender(<UI />);
  await waitFor(() => expect(screen.getByText("/login")).toBeTruthy()); expect(readPendingPushTap()?.eventId).toBe(3);
  mock.get.mockResolvedValue({ allowed: true, destination: { type: "matchup", league_id: 5, resource_id: 9, week: 6 } });
  mock.auth = { user: { id: 7 }, isBootstrapping: false }; view.rerender(<UI />);
  await waitFor(() => expect(screen.getByText("/league/5/matchup?week=6&matchup=9")).toBeTruthy());
  expect(readPendingPushTap()).toBeNull();
});
it("rejects a different signed-in account without requesting the private event", async () => {
  queuePushTap({ event_id: 3, recipient_user_id: 7 }); mock.auth = { user: { id: 8 }, isBootstrapping: false };
  render(<UI />); await waitFor(() => expect(screen.getByText("/alerts")).toBeTruthy()); expect(mock.get).not.toHaveBeenCalled();
});
it("falls back to Alerts for removed access and rejects arbitrary payload URLs", async () => {
  queuePushTap({ event_id: 3, recipient_user_id: 7 }); mock.auth = { user: { id: 7 }, isBootstrapping: false };
  mock.get.mockResolvedValue({ allowed: false, destination: null }); render(<UI />);
  await waitFor(() => expect(screen.getByText("/alerts")).toBeTruthy());
  queuePushTap({ url: "https://evil.test", destination: { type: "draft", league_id: 5 } }); expect(readPendingPushTap()).toBeNull();
});

it("reuses the native foreground listener to refresh queries and removes it on teardown", async()=>{
  mock.native=true;mock.auth={user:{id:7},isBootstrapping:false};
  const view=render(<UI/>);await waitFor(()=>expect(mock.listener).toHaveBeenCalledTimes(1));
  const callback=mock.listener.mock.calls[0][1];
  act(()=>callback({isActive:false}));expect(focusManager.isFocused()).toBe(false);
  act(()=>callback({isActive:true}));expect(focusManager.isFocused()).toBe(true);
  view.unmount();expect(mock.remove).toHaveBeenCalledTimes(1);
});
