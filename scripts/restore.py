#!/usr/bin/env python3
"""
Restore script for reverting to git checkpoints.

Usage:
    python scripts/restore.py                    # List all available checkpoints
    python scripts/restore.py <tag>              # Restore to specific tag

Example:
    python scripts/restore.py                    # List checkpoints
    python scripts/restore.py prompt-12           # Restore to prompt-12
"""

import subprocess
import sys


def list_checkpoints():
    """List all available checkpoint tags."""
    # Fetch remote tags first
    print("Fetching remote tags...")
    try:
        subprocess.run(["git", "fetch", "--tags"], check=True, capture_output=True)
        print("✓ Remote tags fetched")
    except subprocess.CalledProcessError:
        print("⚠ Warning: Failed to fetch remote tags (showing local tags only)")
    
    result = subprocess.run(
        ["git", "tag", "-l"],
        capture_output=True,
        text=True,
        check=True
    )
    tags = result.stdout.strip().split("\n") if result.stdout.strip() else []
    
    if not tags:
        print("No checkpoints found.")
        return
    
    print("Available checkpoints:")
    for tag in tags:
        print(f"  - {tag}")


def restore_checkpoint(tag):
    """Restore to a specific checkpoint tag."""
    print(f"Restoring to checkpoint: {tag}")
    subprocess.run(["git", "checkout", tag], check=True)
    print(f"✓ Restored to: {tag}")
    print()
    print("WARNING: You are in detached HEAD state.")
    print("To continue work, create a new branch:")
    print(f"  git checkout -b continue-from-{tag}")


def main():
    if len(sys.argv) == 1:
        # No argument provided, list checkpoints
        list_checkpoints()
    elif len(sys.argv) == 2:
        # Tag provided, restore to that tag
        tag = sys.argv[1]
        restore_checkpoint(tag)
    else:
        print("Usage: python scripts/restore.py [tag]")
        print("  (no tag)  - List all available checkpoints")
        print("  <tag>     - Restore to specific checkpoint")
        sys.exit(1)


if __name__ == "__main__":
    main()
