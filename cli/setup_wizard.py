"""
Setup Wizard for first-time configuration.

Provides an interactive Rich-based wizard for configuring Jarvis on first launch.
Writes jarvis.config.yaml for structured settings and .env for API keys.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from core.observability import (
    TraceEmitter,
    MemoryTraceEmitter,
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
)

if TYPE_CHECKING:
    pass


class SetupWizard:
    """Interactive setup wizard for Jarvis configuration."""

    def __init__(
        self,
        config_path: str = "jarvis.config.yaml",
        env_path: str = ".env",
        emitter: "TraceEmitter | None" = None,
    ) -> None:
        """Initialize the setup wizard.

        Args:
            config_path: Path to the configuration file
            env_path: Path to the environment file
            emitter: Trace emitter for events
        """
        self._config_path = Path(config_path)
        self._env_path = Path(env_path)
        self._emitter = emitter or MemoryTraceEmitter()
        self._console = Console()

    def config_exists(self) -> bool:
        """Check if configuration file exists.

        Returns:
            True if jarvis.config.yaml exists
        """
        return self._config_path.exists()

    def run(self) -> dict:
        """Run the full interactive wizard.

        Returns:
            Dict of all configuration values
        """
        config = {}

        # Welcome
        self._console.print(
            Panel(
                "[bold blue]Jarvis Setup Wizard[/bold blue]",
                title="Welcome",
                border_style="blue",
            )
        )

        # LLM Adapter
        config["adapter"] = Prompt.ask(
            "LLM Adapter",
            choices=["ollama", "openai", "anthropic", "gemini"],
            default="ollama",
        )

        # Ollama check
        ollama_reachable = False
        available_models = []
        if config["adapter"] == "ollama":
            try:
                import httpx
                response = httpx.get("http://localhost:11434/api/tags", timeout=3)
                if response.status_code == 200:
                    ollama_reachable = True
                    data = response.json()
                    if "models" in data:
                        available_models = [m["name"] for m in data["models"]]
                        self._console.print(f"[green]✓[/green] Ollama reachable. Found {len(available_models)} models.")
                        for model in available_models[:5]:
                            self._console.print(f"  - {model}")
                        if len(available_models) > 5:
                            self._console.print(f"  ... and {len(available_models) - 5} more")
                else:
                    self._console.print("[yellow]⚠[/yellow] Ollama not reachable. Continuing anyway.")
            except Exception:
                self._console.print("[yellow]⚠[/yellow] Ollama not reachable. Continuing anyway.")

        # Model
        if config["adapter"] == "ollama" and available_models:
            config["model"] = Prompt.ask(
                "Model",
                choices=available_models,
                default="qwen2.5-coder:7b" if "qwen2.5-coder:7b" in available_models else available_models[0],
            )
        else:
            config["model"] = Prompt.ask(
                "Model",
                default="qwen2.5-coder:7b",
            )

        # Postgres
        config["postgres_url"] = Prompt.ask(
            "Postgres URL (optional, press Enter to skip)",
            default="",
        )

        # Qdrant
        config["qdrant_url"] = Prompt.ask(
            "Qdrant URL (optional, press Enter to skip)",
            default="",
        )

        # Obsidian vault
        config["obsidian_path"] = Prompt.ask(
            "Obsidian vault path (optional, press Enter to skip)",
            default="",
        )

        # Telegram bot token
        config["telegram_bot_token"] = Prompt.ask(
            "Telegram bot token (optional, press Enter to skip)",
            default="",
        )

        # API keys for non-Ollama adapters
        if config["adapter"] == "openai":
            config["openai_api_key"] = Prompt.ask(
                "OpenAI API Key (optional, press Enter to skip)",
                default="",
            )
        elif config["adapter"] == "anthropic":
            config["anthropic_api_key"] = Prompt.ask(
                "Anthropic API Key (optional, press Enter to skip)",
                default="",
            )
        elif config["adapter"] == "gemini":
            config["gemini_api_key"] = Prompt.ask(
                "Gemini API Key (optional, press Enter to skip)",
                default="",
            )

        # Approval gate mode
        config["approval_mode"] = Prompt.ask(
            "Approval gate mode",
            choices=["always ask", "auto-approve low-risk"],
            default="always ask",
        )

        # Review
        table = Table(title="Configuration Review")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Adapter", config["adapter"])
        table.add_row("Model", config["model"])
        table.add_row("Postgres URL", config["postgres_url"] or "(skipped)")
        table.add_row("Qdrant URL", config["qdrant_url"] or "(skipped)")
        table.add_row("Obsidian Path", config["obsidian_path"] or "(skipped)")
        table.add_row("Telegram Token", "***" if config["telegram_bot_token"] else "(skipped)")
        table.add_row("Approval Mode", config["approval_mode"])

        self._console.print(table)

        # Confirm
        confirm = Prompt.ask(
            "Save this configuration? [Y/n]",
            default="y",
        )

        if confirm.lower() == "n":
            return self.run()  # Re-run

        return config

    def save(self, config: dict) -> None:
        """Save configuration to files.

        Splits config into jarvis.config.yaml (non-secret) and .env (API keys).

        Args:
            config: Configuration dictionary
        """
        import yaml
        from datetime import datetime

        # Prepare non-secret config for YAML
        yaml_config = {
            "adapter": config["adapter"],
            "model": config["model"],
            "postgres_url": config["postgres_url"],
            "qdrant_url": config["qdrant_url"],
            "obsidian_path": config["obsidian_path"],
            "approval_mode": config["approval_mode"],
        }

        # Write YAML config
        with open(self._config_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False)

        # Prepare .env content (API keys only)
        env_lines = []
        if config.get("openai_api_key"):
            env_lines.append(f"OPENAI_API_KEY={config['openai_api_key']}")
        if config.get("anthropic_api_key"):
            env_lines.append(f"ANTHROPIC_API_KEY={config['anthropic_api_key']}")
        if config.get("gemini_api_key"):
            env_lines.append(f"GEMINI_API_KEY={config['gemini_api_key']}")
        if config.get("telegram_bot_token"):
            env_lines.append(f"TELEGRAM_BOT_TOKEN={config['telegram_bot_token']}")

        # Write .env file
        if env_lines:
            with open(self._env_path, "w") as f:
                f.write("\n".join(env_lines))

        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message="Configuration saved",
                data={
                    "config_path": str(self._config_path),
                    "env_path": str(self._env_path),
                    "adapter": config["adapter"],
                },
                duration_ms=0,
            )
            import asyncio
            asyncio.run(self._emitter.emit(event))
        except Exception:
            pass

    def load(self) -> dict:
        """Load configuration from file.

        Returns:
            Dict of configuration values, empty dict if file does not exist
        """
        import yaml

        if not self._config_path.exists():
            return {}

        with open(self._config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message="Configuration loaded",
                data={
                    "config_path": str(self._config_path),
                },
                duration_ms=0,
            )
            import asyncio
            asyncio.run(self._emitter.emit(event))
        except Exception:
            pass

        return config

    def run_doctor(self) -> dict:
        """Check configured services and report status.

        Returns:
            Dict with service status: {"ollama": bool, "postgres": bool, "qdrant": bool, "obsidian": bool}
        """
        status = {
            "ollama": False,
            "postgres": False,
            "qdrant": False,
            "obsidian": False,
        }

        config = self.load()

        # Check Ollama
        if config.get("adapter") == "ollama":
            try:
                import httpx
                response = httpx.get("http://localhost:11434/api/tags", timeout=3)
                status["ollama"] = response.status_code == 200
            except Exception:
                pass

        # Check Postgres
        if config.get("postgres_url"):
            try:
                import asyncpg
                import asyncio

                async def check_postgres():
                    conn = await asyncpg.connect(config["postgres_url"])
                    await conn.close()
                    return True

                status["postgres"] = asyncio.run(check_postgres())
            except Exception:
                pass

        # Check Qdrant
        if config.get("qdrant_url"):
            try:
                import httpx
                response = httpx.get(f"{config['qdrant_url']}/health", timeout=3)
                status["qdrant"] = response.status_code == 200
            except Exception:
                pass

        # Check Obsidian
        if config.get("obsidian_path"):
            obsidian_path = Path(config["obsidian_path"])
            status["obsidian"] = obsidian_path.exists()

        # Print results table
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")

        table.add_row("Ollama", "[green]✓[/green]" if status["ollama"] else "[red]✗[/red]")
        table.add_row("Postgres", "[green]✓[/green]" if status["postgres"] else "[red]✗[/red]")
        table.add_row("Qdrant", "[green]✓[/green]" if status["qdrant"] else "[red]✗[/red]")
        table.add_row("Obsidian", "[green]✓[/green]" if status["obsidian"] else "[red]✗[/red]")

        self._console.print(table)

        # Emit trace event
        try:
            event = TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.INFO,
                message="Doctor check completed",
                data=status,
                duration_ms=0,
            )
            import asyncio
            asyncio.run(self._emitter.emit(event))
        except Exception:
            pass

        return status
