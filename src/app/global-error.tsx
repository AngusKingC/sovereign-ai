"use client";
import { useEffect, useRef } from "react";
import { logComponentError, flushSync } from "@/hooks/useErrorLogger";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const loggedRef = useRef(false);

  useEffect(() => {
    if (!loggedRef.current) {
      try {
        logComponentError(error, undefined, "GlobalErrorBoundary");
        flushSync(); // Rev3: immediately flush — global-error may fire before startErrorLogging
      } catch (e) {
        console.error("[ERROR LOG] Failed to log global error:", e);
      }
      loggedRef.current = true;
    }
  }, [error]);

  const isDev = process.env.NODE_ENV === "development";

  return (
    <html>
      <body style={{ padding: "2rem", background: "#0c0c0f", color: "#e0e0e0", fontFamily: "monospace" }}>
        <h2 style={{ color: "#ef4444" }}>Fatal Error — Layout Crashed</h2>
        <div style={{ color: "#94a3b8", marginBottom: "1rem" }}>{error.message}</div>
        {isDev && (
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "13px", color: "#64748b" }}>
            {error.stack}
          </pre>
        )}
        <button onClick={reset} style={{ marginTop: "1rem", padding: "0.5rem 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
          Try Again
        </button>
      </body>
    </html>
  );
}
