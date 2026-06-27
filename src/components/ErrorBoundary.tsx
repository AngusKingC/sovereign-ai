"use client";
import React from "react";
import { logComponentError } from "@/hooks/useErrorLogger";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  componentName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

const MAX_RETRIES = 3;
const isDev = process.env.NODE_ENV === "development";

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  // Rev3: do NOT reset retryCount here — only set hasError + error
  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logComponentError(error, errorInfo.componentStack || undefined, this.props.componentName);
  }

  handleRetry = () => {
    // Rev3: increment retryCount, check limit BEFORE resetting hasError
    this.setState((prev) => {
      const nextCount = prev.retryCount + 1;
      if (nextCount > MAX_RETRIES) return prev; // Don't retry if over limit
      return { hasError: false, error: null, retryCount: nextCount };
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const name = this.props.componentName || "Component";
      const retriesLeft = Math.max(0, MAX_RETRIES - this.state.retryCount);

      return (
        <div style={{
          padding: "1rem", margin: "0.5rem", background: "#1a1a2e",
          border: "1px solid #ef4444", borderRadius: "4px",
          color: "#e0e0e0", fontFamily: "monospace", fontSize: "13px",
        }}>
          <div style={{ color: "#ef4444", fontWeight: "bold", marginBottom: "0.5rem" }}>
            [{name}] Error
          </div>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>{this.state.error?.message || "Unknown error"}</div>
          {isDev && (
            <details style={{ color: "#64748b" }}>
              <summary style={{ cursor: "pointer", color: "#94a3b8" }}>Stack trace</summary>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "11px", marginTop: "0.5rem" }}>
                {this.state.error?.stack}
              </pre>
            </details>
          )}
          {retriesLeft > 0 ? (
            <button onClick={this.handleRetry} style={{
              marginTop: "0.5rem", padding: "0.25rem 0.75rem", background: "#3b82f6",
              color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "12px",
            }}>
              Retry ({retriesLeft} left)
            </button>
          ) : (
            <div style={{ marginTop: "0.5rem", color: "#64748b", fontSize: "12px" }}>
              Retry limit reached — fix the root cause
            </div>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
