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
    parser = argparse.ArgumentParser(
        description="Sovereign AI Agent Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jarvis                    # Start Textual TUI (arrow key navigation)
  jarvis --rich             # Start Rich-based CLI (slash commands)
  jarvis "explain this code" # Run single query
  jarvis --help             # Show help
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
    
    args = parser.parse_args()
    
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

