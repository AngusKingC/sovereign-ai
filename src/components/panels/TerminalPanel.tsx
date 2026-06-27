"use client";
import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useWebSocket } from "@/hooks/useWebSocket";
import "@xterm/xterm/css/xterm.css";

export function TerminalPanel() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  // PTY WebSocket URL — uses absolute BACKEND_URL (WebSocket cannot be proxied through Next.js rewrites)
  const wsUrl = "http://localhost:8000/ws/pty".replace("http", "ws");

  const { send, isConnected } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      termRef.current?.write(data);
    },
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "monospace",
      theme: { background: "#0c0c0f", foreground: "#e0e0e0" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());
    term.open(containerRef.current);

    // Defer initial fit to ensure container has dimensions
    const fitWithGuard = () => {
      try {
        if (containerRef.current && containerRef.current.offsetWidth > 0 && containerRef.current.offsetHeight > 0) {
          fit.fit();
        }
      } catch (e) {
        console.error("[TerminalPanel] FitAddon error:", e);
      }
    };

    // Initial fit after DOM is rendered
    requestAnimationFrame(fitWithGuard);
    // Fallback with setTimeout if requestAnimationFrame is too early
    setTimeout(fitWithGuard, 100);

    termRef.current = term;
    fitRef.current = fit;

    term.onData((data) => {
      send(data);
    });

    const handleResize = () => fitWithGuard();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      term.dispose();
    };
  }, [send]);

  return (
    <div data-testid="terminal-panel" data-terminal className="h-full p-2">
      <div className="text-xs text-slate-500 mb-1">
        Terminal {isConnected ? "● connected" : "○ disconnected"}
      </div>
      <div ref={containerRef} className="h-[calc(100%-24px)]" />
    </div>
  );
}
