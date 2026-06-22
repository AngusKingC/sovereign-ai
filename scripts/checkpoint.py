#!/usr/bin/env python3
"""
Checkpoint script for creating git checkpoints.

Usage:
    python scripts/checkpoint.py <label>

Example:
    python scripts/checkpoint.py prompt-13
"""

import subprocess
import sys


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/checkpoint.py <label>")
        print("Example: python scripts/checkpoint.py prompt-13")
        sys.exit(1)

    label = sys.argv[1]

    # Stage all changes
    print("Staging all changes...")
    subprocess.run(["git", "add", "-A"], check=True)

    # Commit with checkpoint message
    commit_message = f"checkpoint: {label}"
    print(f"Committing with message: {commit_message}")
    subprocess.run(["git", "commit", "-m", commit_message], check=True)

    # Create tag
    print(f"Creating tag: {label}")
    subprocess.run(["git", "tag", label], check=True)

    # Push to remote
    print("Pushing to remote...")
    try:
        # Get current branch name
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True)
        branch = result.stdout.strip()
        
        subprocess.run(["git", "push", "origin", branch], check=True)
        subprocess.run(["git", "push", "origin", "--tags"], check=True)
        print("✓ Pushed to remote")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Warning: Failed to push to remote: {e}")
        print(f"✓ Local checkpoint saved: {label}")
        print("  (Remote push failed, but local snapshot is still valid)")
        return

    print(f"✓ Checkpoint saved: {label}")


if __name__ == "__main__":
    main()
