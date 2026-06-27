"use client";

export interface ErrorLogEntry {
  timestamp: string;
  type: "error" | "unhandledrejection" | "component";
  message: string;
  stack?: string;
  filename?: string;
  line?: number;
  column?: number;
  componentStack?: string;
  componentName?: string;
}

const MAX_BUFFER_SIZE = 100;
const MAX_UNIQUE_FIRST = 20; // Rev3: preserve first N unique errors (root cause)
const errorBuffer: ErrorLogEntry[] = [];
const uniqueErrors: ErrorLogEntry[] = []; // Rev3: separate buffer for first-seen errors
const seenMessages = new Set<string>(); // Rev3: dedup by message hash
let flushInterval: ReturnType<typeof setInterval> | null = null;
let isStarted = false;

// Rev3: WeakSet instead of mutating error objects (frozen errors won't throw)
const handledErrors = new WeakSet<Error>();

function getErrorHash(entry: { message: string; stack?: string }): string {
  // Rev3: simple hash for dedup — first 100 chars of message + first 200 of stack
  return (entry.message.slice(0, 100) + "|" + (entry.stack || "").slice(0, 200));
}

function addToBuffer(entry: ErrorLogEntry) {
  const hash = getErrorHash(entry);
  if (seenMessages.has(hash)) {
    // Rev3: skip duplicate — we've seen this exact error before
    return;
  }
  seenMessages.add(hash);

  // Rev3: first MAX_UNIQUE_FIRST unique errors go to uniqueErrors (never evicted)
  if (uniqueErrors.length < MAX_UNIQUE_FIRST) {
    uniqueErrors.push(entry);
  }

  // All errors also go to the main buffer (capped)
  if (errorBuffer.length >= MAX_BUFFER_SIZE) {
    errorBuffer.shift(); // Drop oldest from main buffer
  }
  errorBuffer.push(entry);
  console.error("[ERROR LOG]", entry);
}

function getAllBuffered(): ErrorLogEntry[] {
  // Rev3: flush unique errors first (root cause), then recent errors
  const uniqueNotYetFlushed = uniqueErrors.filter(e => !errorBuffer.includes(e));
  return [...uniqueNotYetFlushed, ...errorBuffer];
}

function clearAllBuffers() {
  errorBuffer.length = 0;
  uniqueErrors.length = 0;
  seenMessages.clear();
}

function flushSync() {
  const allErrors = getAllBuffered();
  if (allErrors.length === 0) return;

  // Rev3: only clear if sendBeacon succeeds (or is unavailable — then try fetch)
  if (typeof navigator !== "undefined" && navigator.sendBeacon) {
    const blob = new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" });
    const success = navigator.sendBeacon("/api/errors/log", blob);
    if (success) {
      clearAllBuffers();
      return;
    }
    // sendBeacon failed — don't clear buffer, errors are still in memory
  }
  // Fallback: try synchronous fetch (best effort)
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/errors/log", false); // synchronous
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({ errors: allErrors }));
    if (xhr.status === 200) {
      clearAllBuffers();
    }
  } catch {
    // Both failed — errors remain in buffer for next attempt
  }
}

export function startErrorLogging() {
  // Rev3: check window BEFORE setting isStarted (SSR guard)
  if (typeof window === "undefined") return () => {};
  if (isStarted) return () => {};
  isStarted = true;

  const errorHandler = (event: ErrorEvent) => {
    // Rev3: WeakSet check instead of mutation
    if (event.error && handledErrors.has(event.error)) return;
    addToBuffer({
      timestamp: new Date().toISOString(),
      type: "error",
      message: event.message,
      filename: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack,
    });
  };

  const rejectionHandler = (event: PromiseRejectionEvent) => {
    addToBuffer({
      timestamp: new Date().toISOString(),
      type: "unhandledrejection",
      message: String(event.reason?.message || event.reason),
      stack: event.reason?.stack,
    });
  };

  window.addEventListener("error", errorHandler);
  window.addEventListener("unhandledrejection", rejectionHandler);

  const beforeUnloadHandler = () => flushSync();
  window.addEventListener("beforeunload", beforeUnloadHandler);

  flushInterval = setInterval(async () => {
    const allErrors = getAllBuffered();
    if (allErrors.length === 0) return;

    // Clear buffers before sending (if send fails, we restore)
    const uniqueBackup = [...uniqueErrors];
    const mainBackup = [...errorBuffer];
    const seenBackup = new Set(seenMessages);
    clearAllBuffers();

    try {
      const res = await fetch("/api/errors/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ errors: allErrors }),
      });
      if (!res.ok) {
        // Rev3: restore buffers if send failed AND logger is still active
        if (isStarted) {
          uniqueErrors.push(...uniqueBackup);
          errorBuffer.push(...mainBackup);
          seenMessages.clear();
          seenBackup.forEach(m => seenMessages.add(m));
        }
        // If !isStarted, cleanup already ran — try sendBeacon as last resort
        else if (typeof navigator !== "undefined" && navigator.sendBeacon) {
          navigator.sendBeacon("/api/errors/log", new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" }));
        }
      }
    } catch {
      // Network failure — same restore logic
      if (isStarted) {
        uniqueErrors.push(...uniqueBackup);
        errorBuffer.push(...mainBackup);
        seenMessages.clear();
        seenBackup.forEach(m => seenMessages.add(m));
      } else if (typeof navigator !== "undefined" && navigator.sendBeacon) {
        navigator.sendBeacon("/api/errors/log", new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" }));
      }
    }
  }, 5000);

  return () => {
    window.removeEventListener("error", errorHandler);
    window.removeEventListener("unhandledrejection", rejectionHandler);
    window.removeEventListener("beforeunload", beforeUnloadHandler);
    if (flushInterval) clearInterval(flushInterval);
    flushInterval = null;
    isStarted = false;
    flushSync(); // Flush on SPA navigation
  };
}

export function logComponentError(error: Error, componentStack?: string, componentName?: string) {
  // Rev3: WeakSet instead of mutation (won't throw on frozen objects)
  handledErrors.add(error);
  addToBuffer({
    timestamp: new Date().toISOString(),
    type: "component",
    message: error.message,
    stack: error.stack,
    componentStack,
    componentName,
  });
}

// Rev3: export flushSync for error.tsx/global-error.tsx to call on early crashes
export { flushSync };
