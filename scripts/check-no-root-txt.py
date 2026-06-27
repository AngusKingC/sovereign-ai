#!/usr/bin/env python
"""
Pre-commit hook to prevent .txt files in root directory.
These files should be in txt/ folder instead.
"""
import re
import subprocess
import sys

result = subprocess.run(
    ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
)

staged_files = result.stdout.strip().split("\n")
forbidden_pattern = re.compile(
    r"^(requirements|requirements-dev|vulture-whitelist)\.txt$"
)

for file in staged_files:
    if forbidden_pattern.match(file):
        print("ERROR: .txt files must be in txt/ folder, not root.")
        print(f"Found: {file}")
        print("Move the file to txt/ and commit from there.")
        sys.exit(1)

sys.exit(0)
