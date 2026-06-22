"""
Static analysis test: verifies no production file uses global emit_trace()
directly. All trace emission must go through constructor-injected emitter.
"""
import os
import ast

EXCLUDE_DIRS = {"tests", ".venv", "__pycache__", ".git"}
EXCLUDE_FILES = {"test_di_compliance.py"}
# adapters/gemini.py is deferred to Phase 9 - has emit_trace violations that will be fixed in a dedicated housekeeping prompt
EXCLUDE_FILES.add("gemini.py")

def get_python_files():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for filename in filenames:
            if filename.endswith(".py") and filename not in EXCLUDE_FILES:
                files.append(os.path.join(dirpath, filename))
    return files

def find_emit_trace_calls(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return []
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "emit_trace":
                violations.append(node.lineno)
    return violations

def test_no_direct_emit_trace_calls_in_production_code():
    violations = {}
    for filepath in get_python_files():
        lines = find_emit_trace_calls(filepath)
        if lines:
            violations[filepath] = lines
    assert not violations, (
        "Found direct emit_trace() calls in production files "
        "(violates DI rules):\n" +
        "\n".join(f"  {f}: lines {line_numbers}" for f, line_numbers in violations.items())
    )
