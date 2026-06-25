"""
AR18 Compliance Test - Regression prevention for Rule AR18.

Rule AR18: No broad `except Exception:` without inline comment + WARNING trace.

This test scans all production .py files (repo-wide walk, mirroring test_di_compliance.py)
to ensure no `except Exception:` block is followed by a bare `pass`. AR18's full requirement
(inline comment + WARNING trace) is not AST-enforced — too many variants of 'WARNING trace'
(logger.warning, emitter.emit, print to stderr). Test enforces the worst case: bare `pass`
with no handling.
"""

import ast
import os
from pathlib import Path
from typing import List, Tuple


def extract_exception_blocks(filepath: Path) -> List[Tuple[int, str, str]]:
    """Extract all except Exception blocks from a file.

    Returns:
        List of (line_number, code_snippet, context) tuples
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    blocks = []
    lines = content.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if (
                node.type
                and isinstance(node.type, ast.Name)
                and node.type.id == "Exception"
            ):
                # Get the line number
                line_num = node.lineno
                # Get the code snippet for this block (capture more context)
                start_line = max(0, line_num - 1)
                end_line = min(line_num + 10, len(lines))
                snippet = "\n".join(lines[start_line:end_line])
                blocks.append((line_num, snippet, str(filepath)))

    return blocks


def check_ar18_compliance(filepath: Path) -> List[Tuple[int, str, str]]:
    """Check if except Exception blocks comply with AR18.

    AR18 requires:
    1. An inline comment explaining the exception handling
    2. A WARNING trace (logging.warning or similar)

    Returns:
        List of (line_number, snippet, filepath) for violations
    """
    violations = []
    blocks = extract_exception_blocks(filepath)

    for line_num, snippet, filepath_str in blocks:
        # Check for bare "except Exception:" followed immediately by "pass"
        # This is the main AR18 violation we want to catch
        lines = snippet.split("\n")
        for i, line in enumerate(lines):
            if "except Exception" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line == "pass":
                    violations.append((line_num, snippet, filepath_str))
                    break

    return violations


EXCLUDE_DIRS = {
    "tests",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".git",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".eggs",
    ".pytest_cache",
}
EXCLUDE_FILES = {"test_ar18_compliance.py"}


def get_python_files() -> list[str]:
    """Walk all production .py files, excluding tests and virtualenvs.

    Mirrors tests/test_di_compliance.py:get_python_files() pattern.
    Longer exclude list than test_di_compliance.py because the AR18 test
    must not walk into vendored third-party code (dist/, build/, node_modules/)
    where bare except blocks are common and unfixable.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for filename in filenames:
            if filename.endswith(".py") and filename not in EXCLUDE_FILES:
                files.append(os.path.join(dirpath, filename))
    return files


def test_ar18_compliance_repo_wide():
    """AR18: No bare `except Exception: pass` in any production file.

    Replaces 4 hardcoded file-list tests (Plan 71) with a repo-wide walk
    mirroring tests/test_di_compliance.py. Catches new files added since
    Plan 71 (auto_corrector, sandbox, cost_tracker, task_classifier,
    debate_pool, prism_llama, testing_battery).

    Test function count delta: 4 → 1 (net -3). ar18-fix-all baseline 1367
    becomes 1364 at this plan's close. See PLANS.md reconciliation note.
    """
    all_violations: list[tuple[str, int, str]] = []
    for filepath in get_python_files():
        path = Path(filepath)
        if not path.exists():
            continue
        # check_ar18_compliance returns List[Tuple[int, str, str]] where
        # the third element is str(filepath) (redundant — we already have
        # filepath from the outer loop). We carry filepath explicitly to
        # decouple from the helper's return shape; the helper's third
        # element is ignored via the underscore.
        for line_num, snippet, _ in check_ar18_compliance(path):
            all_violations.append((filepath, line_num, snippet))

    if all_violations:
        violation_msg = "AR18 violations found:\n"
        for filepath_str, line_num, snippet in all_violations:
            violation_msg += f"\n{filepath_str}:{line_num}\n{snippet}\n---\n"
        assert False, violation_msg
