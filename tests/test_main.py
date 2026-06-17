"""Tests for cli/main.py."""

import pytest
from unittest.mock import patch, MagicMock


def test_serve_subcommand_is_registered():
    """Test that passing ['serve'] to the CLI dispatcher reaches the serve entry point without an argparse error."""
    # Mock the serve function to avoid actually starting the server
    with patch('cli.serve.serve') as mock_serve:
        # Mock typer.run to prevent it from actually running
        with patch('typer.run') as mock_typer_run:
            # Set up sys.argv to simulate 'jarvis serve' command
            import sys
            original_argv = sys.argv
            try:
                sys.argv = ['jarvis', 'serve']
                
                # Import and call main
                from cli.main import main
                main()
                
                # Assert that typer.run was called (meaning serve was dispatched)
                mock_typer_run.assert_called_once()
            finally:
                sys.argv = original_argv
