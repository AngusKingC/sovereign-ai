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
const MAX_UNIQUE_FIRST = 20;
const errorBuffer: ErrorLogEntry[] = [];
const uniqueErrors: ErrorLogEntry[] = [];
const seenMessages = new Set<string>();
let flushInterval: ReturnType<typeof setInterval> | null = null;
let isStarted = false;

const handledErrors = new WeakSet<Error>();

function getErrorHash(entry: { message: string; stack?: string }): string {
  return (entry.message.slice(0, 100) + "|" + (entry.stack || "").slice(0, 200));
}

function addToBuffer(entry: ErrorLogEntry) {
  const hash = getErrorHash(entry);
  if (seenMessages.has(hash)) {
    return;
  }
  seenMessages.add(hash);

  if (uniqueErrors.length < MAX_UNIQUE_FIRST) {
    uniqueErrors.push(entry);
  }

  if (errorBuffer.length >= MAX_BUFFER_SIZE) {
    errorBuffer.shift();
  }
  errorBuffer.push(entry);
}

function getAllBuffered(): ErrorLogEntry[] {
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

  if (typeof navigator !== "undefined" && navigator.sendBeacon) {
    const blob = new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" });
    const success = navigator.sendBeacon("/api/errors/log", blob);
    if (success) {
      clearAllBuffers();
      return;
    }
  }
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/errors/log", false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({ errors: allErrors }));
    if (xhr.status === 200) {
      clearAllBuffers();
    }
  } catch {
  }
}

export function startErrorLogging() {
  if (typeof window === "undefined") return () => {};
  if (isStarted) return () => {};
  isStarted = true;

  const errorHandler = (event: ErrorEvent) => {
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
        if (isStarted) {
          uniqueErrors.push(...uniqueBackup);
          errorBuffer.push(...mainBackup);
          seenMessages.clear();
          seenBackup.forEach(m => seenMessages.add(m));
        }
        else if (typeof navigator !== "undefined" && navigator.sendBeacon) {
          navigator.sendBeacon("/api/errors/log", new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" }));
        }
      }
    } catch {
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
    flushSync();
  };
}

export function logComponentError(error: Error, componentStack?: string, componentName?: string) {
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

export function logHttpError(url: string, status: number, message: string) {
  addToBuffer({
    timestamp: new Date().toISOString(),
    type: "error",
    message: `HTTP ${status} error from ${url}: ${message}`,
  });
}

export { flushSync };
