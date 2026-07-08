import { Component, type ErrorInfo, type ReactNode } from "react";

import { PageErrorState, PageShell } from "@/components/PageState";

type Props = {
  children: ReactNode;
};

type State = {
  error: Error | null;
};

export class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Route render failed", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <PageShell>
          <PageErrorState
            title="This screen hit an error"
            description={this.state.error.message || "Refresh the screen and try again."}
            actionLabel="Reload"
            onAction={() => window.location.reload()}
          />
        </PageShell>
      );
    }

    return this.props.children;
  }
}
