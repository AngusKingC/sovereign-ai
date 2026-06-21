"""
Tests for setup wizard.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from cli.setup_wizard import SetupWizard
from core.observability import MemoryTraceEmitter


class TestSetupWizard:
    """Test SetupWizard class."""

    @pytest.fixture
    def trace_emitter(self):
        """Create a memory trace emitter for testing."""
        return MemoryTraceEmitter()

    @pytest.fixture
    def wizard(self, tmp_path, trace_emitter):
        """Create a setup wizard with temporary paths."""
        config_path = tmp_path / "jarvis.config.yaml"
        env_path = tmp_path / ".env"
        return SetupWizard(
            config_path=str(config_path),
            env_path=str(env_path),
            emitter=trace_emitter,
        )

    def test_config_exists_returns_false_when_file_does_not_exist(self, wizard):
        """Test config_exists returns False when file does not exist."""
        assert wizard.config_exists() is False

    def test_config_exists_returns_true_when_file_exists(self, wizard, tmp_path):
        """Test config_exists returns True when file exists."""
        config_path = tmp_path / "jarvis.config.yaml"
        config_path.write_text("adapter: ollama")
        assert wizard.config_exists() is True

    @patch("cli.setup_wizard.Prompt.ask")
    def test_run_returns_dict_with_all_expected_keys(self, mock_ask, wizard):
        """Test run returns dict with all expected keys."""
        mock_ask.side_effect = [
            "ollama",  # adapter
            "qwen2.5-coder:7b",  # model
            "",  # postgres_url
            "",  # qdrant_url
            "",  # obsidian_path
            "",  # telegram_bot_token
            "always ask",  # approval_mode
            "y",  # confirm
        ]

        config = wizard.run()

        assert "adapter" in config
        assert "model" in config
        assert "postgres_url" in config
        assert "qdrant_url" in config
        assert "obsidian_path" in config
        assert "telegram_bot_token" in config
        assert "approval_mode" in config

    @patch("cli.setup_wizard.Prompt.ask")
    def test_run_uses_default_values_when_user_presses_enter(self, mock_ask, wizard):
        """Test run uses default values when user presses Enter."""
        # First call is for adapter with default "ollama"
        # Second call is for model with default "qwen2.5-coder:7b"
        # Third call is for postgres_url with default ""
        # Fourth call is for qdrant_url with default ""
        # Fifth call is for obsidian_path with default ""
        # Sixth call is for telegram_bot_token with default ""
        # Seventh call is for approval_mode with default "always ask"
        # Eighth call is for confirm with default "y"
        mock_ask.side_effect = [
            "ollama",  # adapter (user enters default)
            "qwen2.5-coder:7b",  # model (user enters default)
            "",  # postgres_url (user skips)
            "",  # qdrant_url (user skips)
            "",  # obsidian_path (user skips)
            "",  # telegram_bot_token (user skips)
            "always ask",  # approval_mode (user enters default)
            "y",  # confirm
        ]

        config = wizard.run()

        assert config["adapter"] == "ollama"
        assert config["model"] == "qwen2.5-coder:7b"
        assert config["approval_mode"] == "always ask"

    def test_save_writes_yaml_config_with_non_secret_values(self, wizard):
        """Test save writes jarvis.config.yaml with non-secret values."""
        config = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "postgresql://localhost:5432/jarvis",
            "qdrant_url": "http://localhost:6333",
            "obsidian_path": "/path/to/vault",
            "approval_mode": "always ask",
            "telegram_bot_token": "secret_token",
        }

        wizard.save(config)

        config_path = Path(wizard._config_path)
        assert config_path.exists()

        import yaml
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)

        assert yaml_config["adapter"] == "ollama"
        assert yaml_config["model"] == "qwen2.5-coder:7b"
        assert yaml_config["postgres_url"] == "postgresql://localhost:5432/jarvis"
        assert yaml_config["qdrant_url"] == "http://localhost:6333"
        assert yaml_config["obsidian_path"] == "/path/to/vault"
        assert yaml_config["approval_mode"] == "always ask"
        assert "telegram_bot_token" not in yaml_config

    def test_save_writes_env_file_with_api_keys_when_provided(self, wizard):
        """Test save writes .env with API keys when provided."""
        config = {
            "adapter": "openai",
            "model": "gpt-4",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
            "approval_mode": "always ask",
            "openai_api_key": "sk-test-key",
            "telegram_bot_token": "bot-token",
        }

        wizard.save(config)

        env_path = Path(wizard._env_path)
        assert env_path.exists()

        with open(env_path) as f:
            env_content = f.read()

        assert "OPENAI_API_KEY=sk-test-key" in env_content
        assert "TELEGRAM_BOT_TOKEN=bot-token" in env_content

    def test_save_does_not_write_api_keys_to_yaml_config(self, wizard):
        """Test save does not write API keys to jarvis.config.yaml."""
        config = {
            "adapter": "openai",
            "model": "gpt-4",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
            "approval_mode": "always ask",
            "openai_api_key": "sk-test-key",
        }

        wizard.save(config)

        config_path = Path(wizard._config_path)
        with open(config_path) as f:
            yaml_content = f.read()

        assert "sk-test-key" not in yaml_content
        assert "openai_api_key" not in yaml_content

    def test_save_does_not_write_empty_api_key_entries_to_env(self, wizard):
        """Test save does not write empty API key entries to .env."""
        config = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
            "approval_mode": "always ask",
            "openai_api_key": "",
            "telegram_bot_token": "",
        }

        wizard.save(config)

        env_path = Path(wizard._env_path)
        # File should not be created if no API keys are provided
        assert not env_path.exists()

    def test_load_returns_correct_dict_from_existing_config_file(self, wizard):
        """Test load returns correct dict from existing config file."""
        import yaml

        config_data = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "postgresql://localhost:5432/jarvis",
            "qdrant_url": "http://localhost:6333",
            "obsidian_path": "/path/to/vault",
            "approval_mode": "always ask",
        }

        with open(wizard._config_path, "w") as f:
            yaml.dump(config_data, f)

        loaded_config = wizard.load()

        assert loaded_config["adapter"] == "ollama"
        assert loaded_config["model"] == "qwen2.5-coder:7b"
        assert loaded_config["postgres_url"] == "postgresql://localhost:5432/jarvis"

    def test_load_returns_empty_dict_when_file_does_not_exist(self, wizard):
        """Test load returns empty dict when file does not exist."""
        loaded_config = wizard.load()
        assert loaded_config == {}

    @patch("httpx.get")
    def test_run_doctor_returns_correct_status_dict(self, mock_get, wizard):
        """Test run_doctor returns correct status dict."""
        # Mock Ollama response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create config file
        import yaml
        config_data = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
        }
        with open(wizard._config_path, "w") as f:
            yaml.dump(config_data, f)

        status = wizard.run_doctor()

        assert "ollama" in status
        assert "postgres" in status
        assert "qdrant" in status
        assert "obsidian" in status

    @patch("httpx.get")
    def test_run_doctor_returns_false_for_ollama_when_not_reachable(self, mock_get, wizard):
        """Test run_doctor returns False for Ollama when not reachable."""
        mock_get.side_effect = Exception("Connection refused")

        # Create config file
        import yaml
        config_data = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
        }
        with open(wizard._config_path, "w") as f:
            yaml.dump(config_data, f)

        status = wizard.run_doctor()

        assert status["ollama"] is False

    @patch("httpx.get")
    def test_run_doctor_returns_true_for_ollama_when_reachable(self, mock_get, wizard):
        """Test run_doctor returns True for Ollama when reachable."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create config file
        import yaml
        config_data = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
        }
        with open(wizard._config_path, "w") as f:
            yaml.dump(config_data, f)

        status = wizard.run_doctor()

        assert status["ollama"] is True

    def test_run_doctor_emits_trace_event_with_results(self, wizard, trace_emitter):
        """Test run_doctor emits trace event with results."""
        # Create config file
        import yaml
        config_data = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
        }
        with open(wizard._config_path, "w") as f:
            yaml.dump(config_data, f)

        trace_emitter.clear()
        wizard.run_doctor()

        events = trace_emitter.get_events()
        assert len(events) > 0

    def test_save_emits_trace_event_on_save(self, wizard, trace_emitter):
        """Test save emits trace event on save."""
        config = {
            "adapter": "ollama",
            "model": "qwen2.5-coder:7b",
            "postgres_url": "",
            "qdrant_url": "",
            "obsidian_path": "",
            "approval_mode": "always ask",
        }

        trace_emitter.clear()
        wizard.save(config)

        events = trace_emitter.get_events()
        assert len(events) > 0

    @patch("cli.setup_wizard.Prompt.ask")
    def test_run_re_runs_when_user_confirms_no(self, mock_ask, wizard):
        """Test run re-runs when user confirms no."""
        mock_ask.side_effect = [
            # First run
            "ollama",  # adapter (first run)
            "qwen2.5-coder:7b",  # model (first run)
            "",  # postgres_url (first run)
            "",  # qdrant_url (first run)
            "",  # obsidian_path (first run)
            "",  # telegram_bot_token (first run)
            "always ask",  # approval_mode (first run)
            "n",  # confirm (first run - re-run)
            # Second run
            "anthropic",  # adapter (second run)
            "claude-3-sonnet",  # model (second run)
            "",  # postgres_url (second run)
            "",  # qdrant_url (second run)
            "",  # obsidian_path (second run)
            "",  # telegram_bot_token (second run)
            "",  # anthropic_api_key (second run - anthropic asks for API key)
            "always ask",  # approval_mode (second run)
            "y",  # confirm (second run)
        ]

        config = wizard.run()

        # Should return the second run's values
        assert config["adapter"] == "anthropic"
        assert config["model"] == "claude-3-sonnet"
