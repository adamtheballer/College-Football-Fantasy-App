/** One automatic lifetime authorization per account. StoreKit display is Apple's decision. */
export type ReviewState = { account_id: number; enabled: boolean; review_request_claimed_at: string | null };
export type ReviewClaim = ReviewState & { authorization: "granted" | "already_claimed" | "disabled" };
export type ReviewContext = { accountId: number | null; enabled: boolean; native: boolean; foreground: boolean; safe: boolean; screenKey: string };
export type NativeReviewContext = { accountId: string; token: string; safe: boolean };
export type ReviewReadiness = { ready: boolean; appVersion: string; appBuild: string };
export interface ReviewAdapter {
  synchronize(context: NativeReviewContext): Promise<ReviewReadiness>;
  request(context: NativeReviewContext): Promise<unknown>;
}
export interface ReviewDependencies {
  adapter: ReviewAdapter;
  state(accountId: number, signal: AbortSignal): Promise<ReviewState>;
  claim(accountId: number, version: string, build: string, signal: AbortSignal): Promise<ReviewClaim>;
  consumed(accountId: number): boolean;
  remember(accountId: number): void;
  now(): number;
  /** Defaults to zero: no idle wait once the screen is safe. */
  presentationDelayMs?: number;
}

const inactive: ReviewContext = { accountId: null, enabled: false, native: false, foreground: false, safe: false, screenKey: "" };
const same = (a: ReviewContext, b: ReviewContext) => Object.keys(a).every((key) => a[key as keyof ReviewContext] === b[key as keyof ReviewContext]);
const canAttempt = (c: ReviewContext) => c.accountId !== null && c.native && c.enabled && c.foreground && c.safe;

export class AppReviewCoordinator {
  private context = inactive;
  private generation = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private abort: AbortController | undefined;
  private inFlight = false;
  private disposed = false;
  private readonly visit = new Map<number, { attempts: number; lastAttempt: number; uncertain: boolean }>();
  private readonly remembered = new Set<number>();
  private readonly instance = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}:${Math.random()}`;

  constructor(private readonly dependencies: ReviewDependencies) {}

  update(context: ReviewContext): void {
    if (this.disposed) return;
    if (!same(this.context, context)) {
      this.context = context;
      this.cancel();
    }
    this.schedule();
  }

  /** Touch/key/scroll interrupts the unobstructed window without polling. */
  interrupt(): void {
    if (this.disposed || !this.context.native) return;
    this.cancel();
    this.schedule();
  }

  dispose(): void {
    this.disposed = true;
    this.cancel();
  }

  private nativeContext(safe: boolean): NativeReviewContext {
    return { accountId: String(this.context.accountId ?? ""), token: `${this.instance}:${this.generation}`, safe };
  }

  private cancel(): void {
    this.generation++;
    if (this.timer !== undefined) clearTimeout(this.timer);
    this.timer = undefined;
    this.abort?.abort();
    // No native calls at all in a browser. Revoking context prevents a queued
    // bridge call from acting on an old account or newly obstructed screen.
    if (this.context.native) void this.dependencies.adapter.synchronize(this.nativeContext(false)).catch(() => {});
  }

  private schedule(): void {
    if (this.disposed) return;
    const id = this.context.accountId;
    if (!canAttempt(this.context) || id === null || this.inFlight || this.timer !== undefined || this.remembered.has(id) || this.dependencies.consumed(id)) return;
    const visit = this.visit.get(id);
    // At most two network opportunities per account/mount, separated by 30s
    // and a real safety/lifecycle event. No automatic repeating retry timer.
    if (visit && (visit.attempts >= 2 || this.dependencies.now() - visit.lastAttempt < 30_000)) return;
    const generation = this.generation;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      void this.attempt(id, generation);
    }, this.dependencies.presentationDelayMs ?? 0);
  }

  private current(id: number, generation: number): boolean {
    return !this.disposed && this.generation === generation && this.context.accountId === id && canAttempt(this.context);
  }

  private remember(id: number): void {
    this.remembered.add(id);
    this.dependencies.remember(id);
  }

  private async attempt(id: number, generation: number): Promise<void> {
    if (!this.current(id, generation) || this.inFlight) return;
    this.inFlight = true;
    const abort = new AbortController();
    this.abort = abort;
    const visit = this.visit.get(id) ?? { attempts: 0, lastAttempt: 0, uncertain: false };
    this.visit.set(id, visit);
    try {
      const nativeContext = this.nativeContext(true);
      const ready = await this.dependencies.adapter.synchronize(nativeContext);
      if (!ready.ready || !ready.appVersion || !ready.appBuild || !this.current(id, generation)) return;
      visit.attempts++;
      visit.lastAttempt = this.dependencies.now();
      // This authenticated response confirms the cached/restored account.
      const state = await this.dependencies.state(id, abort.signal);
      if (state.account_id !== id) return;
      if (state.review_request_claimed_at) { this.remember(id); return; }
      if (!state.enabled || !this.current(id, generation) || visit.uncertain) return;
      // Once dispatched, a failed/aborted response is ambiguous. Only read
      // state on a later opportunity; never replay a grant in this visit.
      visit.uncertain = true;
      const result = await this.dependencies.claim(id, ready.appVersion, ready.appBuild, abort.signal);
      if (result.account_id !== id) return;
      if (result.review_request_claimed_at) this.remember(id);
      if (result.authorization !== "granted" || !result.enabled || !result.review_request_claimed_at || !this.current(id, generation)) return;
      // Reconfirm the release switch/session after the committed grant. A
      // failure here consumes silently rather than presenting under uncertainty.
      const confirmed = await this.dependencies.state(id, abort.signal);
      if (!confirmed.enabled || confirmed.account_id !== id || !this.current(id, generation)) return;
      // Cache has already been durably marked. Native independently checks
      // its current scene, context and account-scoped invocation guard.
      const stillReady = await this.dependencies.adapter.synchronize(nativeContext);
      if (!stillReady.ready || !this.current(id, generation)) return;
      await this.dependencies.adapter.request(nativeContext);
    } catch {
      // Review failures never affect authentication, navigation or app use.
    } finally {
      this.inFlight = false;
      if (this.abort === abort) this.abort = undefined;
      // A changed account may have become safe while the old call settled.
      if (this.generation !== generation) this.schedule();
    }
  }
}
