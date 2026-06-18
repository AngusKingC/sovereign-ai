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


def test_serve_subcommand_strips_serve_from_argv():
    """Test that 'jarvis serve' dispatches to serve() without typer crashing on the 'serve' arg.

    Regression test for F1: typer.run(serve) was re-parsing sys.argv which still
    contained 'serve', causing 'Got unexpected extra argument (serve)' exit code 2.
    """
    import sys
    with patch('cli.serve.serve') as mock_serve:
        with patch('typer.run') as mock_typer_run:
            original_argv = sys.argv
            try:
                sys.argv = ['jarvis', 'serve', '--port', '7001']
                from cli.main import main
                main()
                # typer.run should have been called (meaning serve was dispatched)
                mock_typer_run.assert_called_once()
                # After main() returns, sys.argv should have 'serve' stripped
                # (sys.argv is mutated in-place by the fix)
                assert 'serve' not in sys.argv[1:], f"serve should be stripped from argv, got {sys.argv}"
            finally:
                sys.argv = original_argv
