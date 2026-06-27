"use client";
import { useEffect, useRef } from "react";
import { logComponentError, flushSync } from "@/hooks/useErrorLogger";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const loggedRef = useRef(false); // Rev3: prevent duplicate logging on re-render

  useEffect(() => {
    if (!loggedRef.current) {
      try {
        logComponentError(error, undefined, "PageErrorBoundary");
        flushSync(); // Rev3: immediately flush — error.tsx may fire before startErrorLogging
      } catch (e) {
        console.error("[ERROR LOG] Failed to log page error:", e);
      }
      loggedRef.current = true;
    }
  }, [error]);

  const isDev = process.env.NODE_ENV === "development";

  return (
    <div style={{ padding: "2rem", background: "#0c0c0f", color: "#e0e0e0", minHeight: "100vh", fontFamily: "monospace" }}>
      <h2 style={{ color: "#ef4444", marginBottom: "1rem" }}>Page Error</h2>
      <div style={{ color: "#94a3b8", marginBottom: "1rem" }}>{error.message}</div>
      {isDev && (
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "13px", color: "#64748b", background: "#1a1a2e", padding: "1rem", borderRadius: "4px" }}>
          {error.stack}
        </pre>
      )}
      <button onClick={reset} style={{ marginTop: "1rem", padding: "0.5rem 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
        Try Again
      </button>
    </div>
  );
}
