"""Main CLI entry point for the Sovereign AI Agent Framework.

This provides both a Rich-based CLI and a Textual TUI with arrow key navigation.
All commands are registered in the shared command registry for compatibility
with Web GUI and Standalone GUI interfaces.
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    """Main entry point."""
    # Check if user is calling 'serve' command
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Strip the 'serve' subcommand from argv so typer.run only sees options
        # (--host, --port, --reload). Without this, typer sees 'serve' as a
        # positional argument and crashes with "Got unexpected extra argument".
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from cli.serve import serve
        import typer
        typer.run(serve)
        return

    parser = argparse.ArgumentParser(
        description="Sovereign AI Agent Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jarvis                    # Start Textual TUI (arrow key navigation)
  jarvis --rich             # Start Rich-based CLI (slash commands)
  jarvis "explain this code" # Run single query
  jarvis --help             # Show help
  jarvis serve              # Start web server
        """
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        help="Query to process (non-interactive mode)"
    )
    
    parser.add_argument(
        "--rich",
        action="store_true",
        help="Use Rich-based CLI instead of Textual TUI"
    )
    
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode"
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run setup wizard"
    )

    parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="Re-run setup wizard (ignore existing config)"
    )

    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run doctor to check service status"
    )

    args = parser.parse_args()

    # Handle setup/doctor commands
    if args.setup or args.reconfigure or args.doctor:
        try:
            from cli.setup_wizard import SetupWizard
            wizard = SetupWizard()

            if args.doctor:
                wizard.run_doctor()
                return

            # Setup or reconfigure
            if args.reconfigure or not wizard.config_exists():
                config = wizard.run()
                wizard.save(config)
                print("Configuration saved successfully.")
            else:
                print("Configuration already exists. Use --reconfigure to override.")
                config = wizard.load()

            return
        except Exception as e:
            print(f"Setup wizard failed: {e}")
            # Continue to normal CLI startup if wizard fails

    # First-run check (only if not explicitly running setup)
    try:
        from cli.setup_wizard import SetupWizard
        wizard = SetupWizard()
        if not wizard.config_exists():
            print("No configuration found. Running setup wizard...")
            config = wizard.run()
            wizard.save(config)
            print("Configuration saved successfully.")
    except Exception:
        # If SetupWizard cannot be imported or fails, continue without it
        pass

    # Determine mode
    if args.rich:
        # Use Rich-based CLI
        from cli.rich_cli import JarvisRichCLI
        interactive = not args.non_interactive and args.query is None
        cli = JarvisRichCLI(interactive=interactive)
        
        if interactive:
            asyncio.run(cli.run())
        else:
            asyncio.run(cli.run(args.query))
    else:
        # Use Textual TUI (default)
        if args.query is None and not args.non_interactive:
            # Start TUI
            from cli.tui import main as tui_main
            tui_main()
        else:
            # Non-interactive query
            from cli.rich_cli import JarvisRichCLI
            cli = JarvisRichCLI(interactive=False)
            asyncio.run(cli.run(args.query))


if __name__ == "__main__":
    main()

