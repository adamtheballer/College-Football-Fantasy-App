# Frontend UX Contract

The canonical product frontend is `web/client`.

## Screen State Requirements

Every routed screen should handle:

- Loading: render `PageLoadingState` or a feature-specific skeleton.
- Empty: render `PageEmptyState` with a next action when possible.
- Error: render `PageErrorState` with a retry action.
- Auth expired: backend `401` recovery failure dispatches `cfb-auth-expired`, clears local auth, and protected routes send the user back to sign in.
- Mobile: layouts should collapse to one column before horizontal scrolling.
- Keyboard: clickable cards must support `Enter` and `Space`; form controls need labels or `aria-label`.

## State Rules

- The server is the source of truth for leagues, rosters, drafts, waivers, trades, scoring, and notifications.
- Optimistic updates are allowed only when a failed mutation can be rolled back deterministically.
- Mutations must invalidate every affected query key after success.
- Mutation failures must show visible user feedback and leave cached data untouched or refetched.
- Query retry must not loop on `401`, `403`, or `404`.

## Shared Components

- `web/client/components/PageState.tsx`
  - `PageLoadingState`
  - `PageEmptyState`
  - `PageErrorState`
  - `AuthExpiredState`
- `web/client/components/PageErrorBoundary.tsx`
  - catches route render failures and provides a reload action.
