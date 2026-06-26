"use client";
import { useEffect, useRef } from "react";
import { useAgentStore } from "@/stores/agentStore";

export function BottomBar({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | undefined>(undefined);
  const tokenCount = useAgentStore((s) => s.tokenCount);
  const contextLimit = useAgentStore((s) => s.contextLimit);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const GRID_WIDTH = 32;
    const GRID_HEIGHT = 16;
    const CELL_SIZE = 8;

    canvas.width = GRID_WIDTH * CELL_SIZE;
    canvas.height = GRID_HEIGHT * CELL_SIZE;

    const draw = () => {
      ctx.fillStyle = "#0c0c0f";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      for (let x = 0; x < GRID_WIDTH; x++) {
        for (let y = 0; y < GRID_HEIGHT; y++) {
          const activation = Math.random();
          if (activation > 0.7) {
            ctx.fillStyle = `rgba(245, 158, 11, ${activation * 0.5})`;
            ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE - 1, CELL_SIZE - 1);
          }
        }
      }

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  return (
    <footer className={`bottom-bar flex h-16 items-center gap-4 border-t border-border bg-surface-raised px-4 ${className ?? ""}`} data-testid="bottom-bar">
      <div className="flex items-center gap-2">
        <canvas ref={canvasRef} className="border border-border" />
        <div className="font-mono text-xs text-text-muted">Activation grid</div>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 font-mono text-xs">
        <span className="text-text-muted">Tokens:</span>
        <span className="text-text-primary">{tokenCount.toLocaleString()}</span>
        <span className="text-text-muted">/ {contextLimit.toLocaleString()}</span>
      </div>
    </footer>
  );
}
