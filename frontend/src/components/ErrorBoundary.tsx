'use client';

import { Component, ReactNode } from 'react';
import type { ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="h-screen w-screen flex items-center justify-center bg-surface-1">
            <div className="max-w-md p-6 bg-surface-2 rounded-google-lg border border-destructive/30">
              <h2 className="text-lg font-semibold text-destructive mb-2">
                Something went wrong
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                {this.state.error?.message}
              </p>
              <pre className="text-xs bg-surface-3 p-3 rounded-google overflow-auto max-h-40">
                {this.state.error?.stack}
              </pre>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-google"
              >
                Reload Page
              </button>
            </div>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
