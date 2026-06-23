# Plan 62.5 — Eval Harness Validation

## Opening (S0)

1. **Run `/jarvis-open`** — verify `prompt-62` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.
2. **Read AGENTS.md in full** — no new rules this prompt. Apply all existing rules (AR1-AR18, OR1-OR24). Cite rules by number per OR23.
3. **Scope declaration** — will edit:
   - `evals/validation_tasks.json` (new static fixture)
   - `evals/harness.py` (minor refinements, ≤3 lines per method)
   - `evals/metrics.py` (minor refinements, ≤3 lines per function)
   - `tests/test_eval_harness.py` (add validation tests, ~50 new lines)
   - Will NOT edit: anything in `memory/`, `cli/`, `web/`, `system/`, `skills/`, `adapters/`, `core/` (except if harness.py imports need adjustment)

## Plan Body (S1-S6)

### S1 — Create Validation Task Suite (15 entries)

Create `evals/validation_tasks.json` with exactly 15 entries across 5 categories. Schema per entry:
```json
{
  "task_id": "...",
  "predicted": "...",
  "gold": "...",
  "category": "exact|near|no|punctuation|edge",
  "expected_exact_match": 0.0|1.0,
  "min_token_f1": float,
  "notes": "Human judgment rationale"
}
```

**Categories and required entries:**

1. **Exact-match variants (3)** — exact_match == 1.0, token_f1 == 1.0:
   - `exact-1`: Perfect match ("The quick brown fox", "The quick brown fox")
   - `exact-2`: Whitespace variation ("  The quick brown fox  ", "The quick brown fox")
   - `exact-3`: Case variation ("THE QUICK BROWN FOX", "the quick brown fox") — exact_match 0.0, token_f1 1.0

2. **Near-match variants (3)** — exact_match == 0.0, token_f1 > min_token_f1:
   - `near-1`: One extra word ("The quick brown fox jumps", "The quick brown fox") — min_token_f1: 0.75
   - `near-2`: One missing word ("The quick brown", "The quick brown fox") — min_token_f1: 0.67
   - `near-3`: Synonym substitution ("The fast brown fox", "The quick brown fox") — min_token_f1: 0.60

3. **No-match variants (3)** — all metrics < 0.5:
   - `no-1`: Completely different ("Lorem ipsum dolor", "The quick brown fox")
   - `no-2`: Empty prediction ("", "The quick brown fox")
   - `no-3`: Nonsense ("asdf qwer zxcv", "The quick brown fox")

4. **Punctuation variants (3)** — exact_match == 0.0, token_f1 > 0.5:
   - `punct-1`: Comma added ("Hello, world!", "Hello world") — min_token_f1: 0.67
   - `punct-2`: Period added ("The end.", "The end") — min_token_f1: 0.67
   - `punct-3`: Multiple punctuation ("Wait — what?", "Wait what") — min_token_f1: 0.50

5. **Edge cases (3)**:
   - `edge-1`: Both empty ("", "") — exact_match 1.0, token_f1 1.0
   - `edge-2`: Multiple internal spaces ("The   quick   fox", "The quick fox") — exact_match 0.0, token_f1 1.0 (set-based tokenization)
   - `edge-3`: Numbers ("42 is the answer", "42 is the answer") — exact_match 1.0

**Constraint**: All entries ASCII-only. `min_token_f1` must be present for near-match and punctuation entries. If omitted, default threshold is 0.5.

### S2 — Stdlib-Only Feasibility Check (Gating Step)

Before writing tests, run current metrics against the fixture. Create temporary script `temp/validate_feasibility.py`:

```python
import json
from evals.metrics import compute_exact_match, compute_token_f1, compute_bleu, compute_cosine_similarity

with open("evals/validation_tasks.json") as f:
    tasks = json.load(f)

failures = []
for task in tasks:
    scores = {
        "exact_match": compute_exact_match(task["predicted"], task["gold"]),
        "token_f1": compute_token_f1(task["predicted"], task["gold"]),
        "bleu": compute_bleu(task["predicted"], task["gold"]),
        "cosine_similarity": compute_cosine_similarity(task["predicted"], task["gold"]),
    }

    # Check exact_match
    expected_em = task["expected_exact_match"]
    if expected_em == 1.0 and scores["exact_match"] < 0.95:
        failures.append(f"{task['task_id']}: expected exact_match ~1.0, got {scores['exact_match']}")
    if expected_em == 0.0 and scores["exact_match"] > 0.05:
        failures.append(f"{task['task_id']}: expected exact_match ~0.0, got {scores['exact_match']}")

    # Check token_f1 threshold
    min_f1 = task.get("min_token_f1", 0.5)
    if scores["token_f1"] < min_f1 - 0.2:
        failures.append(f"{task['task_id']}: expected token_f1 >= {min_f1}, got {scores['token_f1']}")

    print(f"{task['task_id']} ({task['category']}): exact_match={scores['exact_match']:.2f} token_f1={scores['token_f1']:.2f} bleu={scores['bleu']:.2f} cos={scores['cosine_similarity']:.2f}")

print(f"\nFailures: {len(failures)}")
for f in failures:
    print(f"  - {f}")

if len(failures) >= 3:
    print("\nHARD STOP: ≥3 tasks failed feasibility check. Stdlib metrics insufficient for validation.")
    exit(1)
else:
    print("\nFeasibility check passed. Proceed to S3.")
```

Run the script. If exit code is 1 (≥3 failures), STOP and report — do not proceed. If exit code is 0, delete the temp script and proceed to S3.

### S3 — Add Validation Tests (Parameterized)

Add `TestEvalValidation` class to `tests/test_eval_harness.py`. Use module-scope fixture for JSON loading.

**Fixture scaffold:**
```python
@pytest.fixture(scope="module")
def validation_suite():
    with open("evals/validation_tasks.json") as f:
        return json.load(f)

def _load_task(suite, task_id):
    task = next((t for t in suite if t["task_id"] == task_id), None)
    assert task is not None, f"Task {task_id} not found in validation suite"
    return task
```

**Tests (all async, parameterized per task):**

1. `test_validation_suite_loads` — verify JSON loads, has 15 entries, all have required keys (`task_id`, `predicted`, `gold`, `category`, `expected_exact_match`, `notes`)

2. `test_exact_match_tasks` — parameterized over `exact-1`, `exact-2`, `exact-3`:
   ```python
   @pytest.mark.parametrize("task_id", ["exact-1", "exact-2", "exact-3"])
   @pytest.mark.asyncio
   async def test_exact_match_tasks(self, harness, validation_suite, task_id):
       task = _load_task(validation_suite, task_id)
       result = await harness.evaluate(task["predicted"], task["gold"], task_id=task_id)
       assert result.metrics["exact_match"] == task["expected_exact_match"],            f"{task_id}: expected exact_match={task['expected_exact_match']}, got {result.metrics['exact_match']}"
       if task_id == "exact-3":
           assert result.metrics["token_f1"] == 1.0, f"{task_id}: case variation should yield token_f1=1.0"
   ```

3. `test_near_match_tasks` — parameterized over `near-1`, `near-2`, `near-3`:
   - assert exact_match == 0.0
   - assert token_f1 >= task["min_token_f1"]

4. `test_no_match_tasks` — parameterized over `no-1`, `no-2`, `no-3`:
   - assert exact_match == 0.0, token_f1 < 0.5, bleu < 0.5, cosine_similarity < 0.5

5. `test_punctuation_tasks` — parameterized over `punct-1`, `punct-2`, `punct-3`:
   - assert exact_match == 0.0
   - assert token_f1 >= task["min_token_f1"]

6. `test_edge_cases` — parameterized over `edge-1`, `edge-2`, `edge-3`:
   - `edge-1`: exact_match 1.0, token_f1 1.0
   - `edge-2`: exact_match 0.0, token_f1 1.0 (set-based tokenization: whitespace split, unordered)
   - `edge-3`: exact_match 1.0

7. `test_batch_eval_on_validation_suite` — run all 15 entries through `evaluate_batch`, verify 15 results, all EvalResult instances

8. `test_summary_on_validation_suite` — run suite, call `summary()`, verify all 4 metrics present, each count == 15

9. `test_metric_priority_order` — document in test comment:
   ```python
   # Metric priority order (design note):
   # - exact_match: ground truth for strict evaluation (character-level identity)
   # - token_f1: ground truth for fuzzy evaluation (word overlap, order-independent)
   # - bleu, cosine_similarity: supplementary metrics; document limitations, don't fix
   # For case variations (exact-3): exact_match=0.0 (strict) and token_f1=1.0 (fuzzy) are both correct.
   ```
   Run `exact-3` through harness, assert both exact_match==0.0 and token_f1==1.0 simultaneously.

### S4 — Refine Metrics (Minimal, ≤3 Lines Per Function)

If S2 revealed issues, apply minimal fixes in priority order:

**Priority order for metric fixes:**
1. `exact_match` and `token_f1` are priority metrics (ground truth for strict/fuzzy). Fix if misaligned.
2. `bleu` and `cosine_similarity` are supplementary. Document limitations, do not fix.

**Allowed adjustments (≤3 lines per function):**
- `exact_match`: Add `.strip()` and collapse multiple spaces (`re.sub(r'\s+', ' ', ...)`). Max 2 lines.
- `token_f1`: Strip basic punctuation (`string.punctuation`) before tokenization. Max 3 lines.
- `bleu`: No changes (supplementary metric).
- `cosine_similarity`: No changes (supplementary metric).

**HARD STOP**: If a fix requires >3 lines per function or external dependencies, STOP and report.

**Document metric priority in `evals/metrics.py` docstring** (add to module-level docstring):
```
Metric priority order for evaluation:
- exact_match: strict ground truth (character-level identity after normalization)
- token_f1: fuzzy ground truth (word overlap, order-independent)
- bleu, cosine_similarity: supplementary metrics with known limitations
```

### S5 — File-Scoped Verification (Fail Fast)

After each file edit, run `/jarvis-verify`. Then:

1. Syntax check on all edited files
2. Ruff: `ruff check evals/harness.py evals/metrics.py tests/test_eval_harness.py`
3. Mypy: `mypy evals/harness.py evals/metrics.py --ignore-missing-imports`
4. **Validation tests first**: `python -m pytest tests/test_eval_harness.py::TestEvalValidation -v`
5. **Full harness tests**: `python -m pytest tests/test_eval_harness.py -v`

If step 4 fails, fix before running step 5.

### S6 — Baseline Reconciliation

Run full test suite: `python -m pytest tests/ -q --tb=short`

- Expected: ~1214 passed (+20 from validation tests), 67 skipped (no change)
- If actual count differs by >5 from expected, update PLANS.md baseline per OR17.
- If ruff/mypy errors appear outside edited files, STOP and report — do not fix unilaterally (OR16).

## Closing

**Run `/jarvis-close`** — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist (one-liner verification):**
- [ ] All 15 fixture entries load and parse correctly
- [ ] 9 validation tests pass (parameterized per-task)
- [ ] Full suite: ~1214 passed (+20), 67 skipped
- [ ] Ruff: 0 errors, Mypy: 0 errors (file-scoped)
- [ ] Tag `prompt-62.5` created and pushed
- [ ] CHANGELOG entry appended
- [ ] PLANS.md updated: Plan 62.5 completed, Plan 63a promoted to ACTIVE
- [ ] No new LANDMINES.md entries
- [ ] C9: No new rules (or capture if pattern found)
