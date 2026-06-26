import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBar } from "@/components/shell/StatusBar";
import { useAgentStore } from "@/stores/agentStore";

describe("StatusBar", () => {
  it("renders session ID", () => {
    render(<StatusBar />);
    expect(screen.getByText(/SES-/)).toBeInTheDocument();
  });

  it("toggles run state on button click", () => {
    render(<StatusBar />);
    const button = screen.getByRole("button", { name: /Run|Pause/ });
    const initialRunning = useAgentStore.getState().isRunning;
    button.click();
    expect(useAgentStore.getState().isRunning).toBe(!initialRunning);
  });
});
