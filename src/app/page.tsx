"use client";
import { useEffect } from "react";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useSSE } from "@/hooks/useSSE";
import { getStatus, sseUrl, login } from "@/lib/api";

export default function Home() {
  const setPhase = useAgentStore((s) => s.setPhase);
  const setLatency = useAgentStore((s) => s.setLatency);
  const setActivation = useMemoryStore((s) => s.setActivation);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;

    login()
      .then(() => {
        if (cancelled) return;
        const poll = async () => {
          try {
            const start = performance.now();
            const status = await getStatus();
            const elapsed = performance.now() - start;
            setPhase(status.phase);
            setLatency(Math.round(elapsed));
          } catch {
          }
        };
        poll();
        intervalId = setInterval(poll, 2000);
      })
      .catch(() => {
        console.warn("Backend auth failed — SSE will not work");
      });

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [setPhase, setLatency]);

  useSSE({
    url: sseUrl("/api/memory/activations"),
    onMessage: (data) => {
      const event = data as { index: number; activation: number };
      setActivation(event.index, event.activation);
    },
  });

  return null;
}
