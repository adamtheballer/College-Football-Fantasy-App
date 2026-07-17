import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  hasError: boolean;
};

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Unhandled application error", error, errorInfo);
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main className="flex min-h-screen items-center justify-center bg-cfb-canvas px-6 py-12">
        <section className="max-w-lg rounded-[2rem] border border-red-300/25 bg-cfb-surface-raised p-8 text-center shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-red-200">Something went wrong</p>
          <h1 className="mt-3 text-3xl font-black italic text-cfb-text-primary">This view could not load.</h1>
          <p className="mt-3 text-sm font-medium leading-6 text-cfb-text-secondary">
            Your account and league data were not changed. Try loading the view again.
          </p>
          <Button className="mt-6" onClick={() => this.setState({ hasError: false })}>
            Try Again
          </Button>
        </section>
      </main>
    );
  }
}
