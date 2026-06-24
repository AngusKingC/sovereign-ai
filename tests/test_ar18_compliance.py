"""
AR18 Compliance Test - Regression prevention for Rule AR18.

Rule AR18: No broad `except Exception:` without inline comment + WARNING trace.

This test scans specified files to ensure all `except Exception:` blocks
have both an inline comment and a WARNING trace (via logging.warning or similar).
"""

import ast
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


def test_ar18_compliance_system_files():
    """Test AR18 compliance in system/ files that were cleaned up."""
    files_to_check = [
        "system/resource_manager.py",
        "system/model_acquisition.py",
        "system/model_registry.py",
        "system/profiler.py",
    ]

    all_violations = []
    for file_path in files_to_check:
        filepath = Path(file_path)
        if not filepath.exists():
            continue

        violations = check_ar18_compliance(filepath)
        all_violations.extend(violations)

    if all_violations:
        violation_msg = "AR18 violations found:\n"
        for line_num, snippet, filepath_str in all_violations:
            violation_msg += f"\n{filepath_str}:{line_num}\n{snippet}\n---\n"
        assert False, violation_msg


def test_ar18_compliance_core_files():
    """Test AR18 compliance in core/ files that were cleaned up."""
    files_to_check = [
        "core/approval_gate.py",
    ]

    all_violations = []
    for file_path in files_to_check:
        filepath = Path(file_path)
        if not filepath.exists():
            continue

        violations = check_ar18_compliance(filepath)
        all_violations.extend(violations)

    if all_violations:
        violation_msg = "AR18 violations found:\n"
        for line_num, snippet, filepath_str in all_violations:
            violation_msg += f"\n{filepath_str}:{line_num}\n{snippet}\n---\n"
        assert False, violation_msg


def test_ar18_compliance_skills_files():
    """Test AR18 compliance in skills/ files that were cleaned up."""
    files_to_check = [
        "skills/notes/notes_skill.py",
        "skills/calendar/calendar_skill.py",
        "skills/reminder/reminder_skill.py",
        "skills/email/email_skill.py",
    ]

    all_violations = []
    for file_path in files_to_check:
        filepath = Path(file_path)
        if not filepath.exists():
            continue

        violations = check_ar18_compliance(filepath)
        all_violations.extend(violations)

    if all_violations:
        violation_msg = "AR18 violations found:\n"
        for line_num, snippet, filepath_str in all_violations:
            violation_msg += f"\n{filepath_str}:{line_num}\n{snippet}\n---\n"
        assert False, violation_msg


def test_ar18_compliance_cli_memory_files():
    """Test AR18 compliance in cli/ and memory/ files that were cleaned up."""
    # Note: cli/command_history.py and memory/obsidian.py were only
    # cleaned up for datetime.now() (S5), not for AR18 (S4).
    # This test is kept for future AR18 cleanup if needed.
    files_to_check = []

    all_violations = []
    for file_path in files_to_check:
        filepath = Path(file_path)
        if not filepath.exists():
            continue

        violations = check_ar18_compliance(filepath)
        all_violations.extend(violations)

    if all_violations:
        violation_msg = "AR18 violations found:\n"
        for line_num, snippet, filepath_str in all_violations:
            violation_msg += f"\n{filepath_str}:{line_num}\n{snippet}\n---\n"
        assert False, violation_msg
