import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { App } from "@capacitor/app";
import { apiGet } from "@/lib/api";
import { isNativeSessionRuntime } from "@/lib/native-session";
import { isNameChangeEligibility, nameChangeRemainingMs, type NameChangeEligibility } from "@/lib/name-change";

type EligibilityState = { phase: "checking" | "ready" | "error"; timing: NameChangeEligibility | null; remainingSeconds: number };
const checking: EligibilityState = { phase: "checking", timing: null, remainingSeconds: 0 };

export function useNameChangeEligibility(accountId: number | null, sessionReady: boolean) {
  const [state, setState] = useState<EligibilityState>(checking);
  const account = useRef(accountId);
  const live = useRef(false);
  const serial = useRef(0);
  const abort = useRef<AbortController>();
  const countdown = useRef<ReturnType<typeof setInterval>>();
  const expiration = useRef<ReturnType<typeof setTimeout>>();
  const reload = useRef<() => Promise<void>>(async () => {});
  const stopCountdown = useCallback(() => {
    if (countdown.current) clearInterval(countdown.current);
    if (expiration.current) clearTimeout(expiration.current);
    countdown.current = undefined; expiration.current = undefined;
  }, []);
  const invalidate = useCallback(() => { serial.current++; abort.current?.abort(); stopCountdown(); }, [stopCountdown]);

  const accept = useCallback((timing: NameChangeEligibility) => {
    if (!live.current || timing.account_id !== account.current || !isNameChangeEligibility(timing)) return;
    invalidate();
    // Date.now is deliberately absent. Device time/DST changes cannot move
    // this deadline; dates are parsed only relative to supplied server time.
    const deadline = performance.now() + nameChangeRemainingMs(timing);
    setState({ phase: "ready", timing, remainingSeconds: timing.remaining_wait_seconds });
    if (!timing.can_change_name) {
      // Schedule the exact supplied deadline, including fractional seconds.
      expiration.current = setTimeout(() => {
        stopCountdown();
        void reload.current();
      }, Math.max(0, Math.ceil(deadline - performance.now())));
      countdown.current = setInterval(() => {
        const remainingSeconds = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
        // Confirmation at expiration controls unlock; never show zero while
        // the last authoritative response still rejects a name change.
        if (remainingSeconds > 0) setState({ phase: "ready", timing, remainingSeconds });
      }, 1000);
    }
  }, [invalidate, stopCountdown]);

  const refresh = useCallback(async () => {
    const expectedId = account.current;
    if (!live.current || expectedId === null) return;
    invalidate();
    const requestSerial = serial.current;
    const controller = new AbortController(); abort.current = controller;
    setState((old) => ({ ...old, phase: "checking" }));
    try {
      const timing = await apiGet<NameChangeEligibility>("/auth/me/name-change-eligibility", undefined, controller.signal);
      if (!live.current || controller.signal.aborted || serial.current !== requestSerial || account.current !== expectedId) return;
      if (!isNameChangeEligibility(timing) || timing.account_id !== expectedId) throw new Error("invalid name-change eligibility");
      accept(timing);
    } catch {
      if (live.current && !controller.signal.aborted && serial.current === requestSerial) {
        setState({ phase: "error", timing: null, remainingSeconds: 0 });
      }
    }
  }, [accept, invalidate]);
  reload.current = refresh;

  useLayoutEffect(() => {
    account.current = accountId;
    live.current = sessionReady && accountId !== null;
    setState(checking);
    if (!live.current) { invalidate(); return; }
    void refresh();
    const onForeground = () => { if (document.visibilityState === "visible") void refresh(); };
    const onVisibility = () => {
      if (document.visibilityState === "visible") onForeground(); else invalidate();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onForeground);
    let removeNative: (() => Promise<void>) | undefined;
    let active = true;
    if (isNativeSessionRuntime()) void App.addListener("appStateChange", ({ isActive }) => {
      if (!active) return;
      if (isActive) void refresh(); else invalidate();
    }).then((handle) => { if (active) removeNative = () => handle.remove(); else void handle.remove(); }).catch(() => {});
    return () => {
      active = false; live.current = false; invalidate();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onForeground);
      void removeNative?.();
    };
  }, [accountId, sessionReady, refresh, invalidate]);
  return { ...state, refresh, accept, invalidate };
}
