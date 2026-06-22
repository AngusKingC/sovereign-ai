# Plan 38.7.1: Clean baseline — Gemini migration, LM Studio test fix, adapter verification, skipped-tests audit

> **Executor instructions**: This plan achieves a fully clean test baseline AND verifies every adapter works end-to-end. Four scopes bundled because they collectively close out the warnings/skipped/failure debt AND confirm the framework's external integrations actually function.
>
> **Critical**: Do NOT defer any step. Do NOT skip verification citing "no service available" — install the service, run it, verify, close it. Do NOT cite "per memory" or "Mistake Pattern N" — per new landmine (Step 8.1), Devin memories are not authoritative. All workarounds must live in the handoff or the plan itself.
>
> **API key protocol**: When a test requires an API key, STOP and ask the user with the appropriate URL (see "API key request protocol" below). Do not skip silently. Do not write keys to any file.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-38.7..HEAD -- adapters/ tests/ scripts/ requirements.txt SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `adapters/`, `tests/`, `scripts/`, `requirements.txt`: expected empty. For handoff/CHANGELOG: allowed per known-landmine procedure.

## Status

- **Priority**: P1 (clean baseline + adapter verification before horizontal cleanup)
- **Effort**: M-L (four scopes, plus real-service verification)
- **Risk**: LOW-MEDIUM (Gemini migration is real code change; adapter verification requires install/run/close cycles)
- **Depends on**: prompt-38.7 (commit `d22e0b4`, tag `prompt-38.7`)
- **Planned at**: master HEAD post-prompt-38.7, 2026-06-19
- **In scope**:
  - Production: `adapters/gemini.py` (Gemini SDK migration, NO 20-line guard)
  - Tests: `tests/test_lm_studio_adapter.py` (fix `test_health_check_without_server` via mock; add `test_health_check_with_server` integration test)
  - Tests: `tests/test_anthropic_adapter.py` (convert 5 unit tests to mocked, including `test_close`; keep 7 integration tests env-conditional)
  - Tests: `tests/test_gemini_adapter.py` (convert 5 unit tests to mocked with new SDK, including `test_close`; keep 6 integration tests env-conditional)
  - Tests: `tests/test_trajectory_exporter.py` (verify Plan 45 deferrals still legitimate, no code change)
  - Config: `requirements.txt` (cleanup duplicates, fix spacing, update google-generativeai → google-genai)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (memory policy landmine, test-baseline documentation, integration tests subsection, requirements.txt cleanup note)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: broad-except audit (Plan 39+), ruff/mypy triage (Plans 43-44), trajectory_exporter functional redesign (Plan 45), **config file design for API keys** (deferred to Plan 41+ — current pattern of env vars is acceptable for this plan), Track B manual TUI verification (Track A from prompt-38.7 closed the Rule 19 violation)

## Why this matters

Two things this plan achieves:

1. **Clean test baseline**: 0 warnings, 0 failures, only legitimate skips (Plan 45 deferrals + env-conditional integration tests). First fully clean baseline since prompt-37.

2. **End-to-end adapter verification**: Every adapter (Ollama, LM Studio, Anthropic, Gemini) is actually run against its real service and confirmed working. Not just unit tests — real end-to-end "I started the service, ran the test, it passed, I closed the service" verification.

The test suite has been at "1080 passed, 29 skipped, 1 failed (flaky), 1 warning" for several prompts. Each item is small but they collectively represent debt that compounds. Plus, the framework claims to support multiple LLM adapters but only Ollama and LM Studio have been verified at runtime — Anthropic and Gemini tests have been skipped for the entire project history.

**Expected outcome**: ~1090 passed (1080 + 10 mocked unit tests — 5 Anthropic + 5 Gemini), ~19 skipped (13 env-conditional integration tests + 6 Plan 45 deferrals), 0 failed, 0 warnings. Plus all 4 adapters verified working end-to-end.

## API key request protocol (for Devin)

When a test requires an API key that isn't set in the environment:

1. **STOP.** Do not skip the test silently. Do not defer. Do not write the key to any file.
2. **Report to user with the appropriate URL**:
   - For Anthropic: `"Test requires ANTHROPIC_API_KEY. Get one at: https://console.anthropic.com/settings/keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - For Gemini: `"Test requires GEMINI_API_KEY. Get one at: https://aistudio.google.com/app/apikey. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - For OpenAI (if needed): `"Test requires OPENAI_API_KEY. Get one at: https://platform.openai.com/api-keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
3. **Wait for user to paste the key.**
4. **Set the key as a session env var** (PowerShell):
   ```powershell
   $env:ANTHROPIC_API_KEY = "<pasted key>"
   ```
   - Do NOT write the key to `.env`, `jarvis.config.yaml`, or any file
   - Do NOT commit the key
   - Do NOT echo the key in output — mask it: `ANTHROPIC_API_KEY=***`
5. **Run the test**. Paste literal pass/fail output.
6. **Clear the env var** after the test run:
   ```powershell
   Remove-Item Env:\ANTHROPIC_API_KEY
   ```

This protocol ensures keys are never persisted, never committed, and never logged. The adapters already accept `api_key` as a constructor parameter (correct pattern) — the caller (test) reads from env var, sets it for the session only.

## What's broken

### A. Gemini FutureWarning (1 warning)

```
adapters/gemini.py:12: FutureWarning:
All support for the `google.generativeai` package has ended.
import google.generativeai as genai  # noqa: Plan 38.7: migrate to google.genai
```

Currently suppressed with `# noqa: Plan 38.7`. This plan executes the migration, removing the suppression. Also updates `requirements.txt` (`google-generativeai` → `google-genai`).

### B. `test_health_check_without_server` failure (1 failed)

`tests/test_lm_studio_adapter.py:60-66` asserts `health_check()` returns `False`. But `adapters/lm_studio.py:167-178` `health_check()` makes an HTTP GET to `{base_url}/models` and returns `True` if status is 200. LM Studio is actually running on Devin's machine → returns `True` → assertion fails.

**Root cause**: Test design assumes no server. Not actually flaky — environment-dependent.

**Fix**: Mock the HTTP client so the unit test is environment-independent. Add a separate integration test (`test_health_check_with_server`) that verifies the happy path when LM Studio IS running.

### C. 29 skipped tests

| Source | Count | Reason | Action |
|---|---|---|---|
| `tests/test_anthropic_adapter.py` | 12 | `ANTHROPIC_API_KEY` env var not set | 5 unit tests → mocked (run always, including `test_close`). 7 integration tests → env-conditional, but verified with real API key per protocol above. |
| `tests/test_gemini_adapter.py` | 11 | `GEMINI_API_KEY` env var not set | 5 unit tests → mocked (run always, including `test_close`). 6 integration tests → env-conditional, verified with real API key per protocol. |
| `tests/test_trajectory_exporter.py` | 6 | Plan 45 deferral | Leave as-is — legitimate Plan-N deferral. Verify Plan 45 still in queue. |
| **Total** | **29** | | **After fix: 13 skipped (7+6 integration) + 6 Plan 45 = 19** |

### D. Adapters not verified end-to-end

The handoff claims 4 LLM adapters (Ollama, LM Studio, Anthropic, Gemini). Only Ollama has been verified at runtime (via prompt-38.7 Track A which mocks it). LM Studio's test fails because it's actually running. Anthropic and Gemini tests have been skipped for the entire project history.

This plan verifies all 4 adapters actually work:
- **Ollama**: Already verified via prompt-38.7 Track A (mocked). Confirm Ollama is installed and `ollama serve` works for completeness.
- **LM Studio**: Already running on Devin's machine (that's why the test fails). Verify `test_health_check_with_server` integration test passes against real LM Studio.
- **Anthropic**: Use API key request protocol. Verify all 8 integration tests pass with real API.
- **Gemini**: Use API key request protocol. Verify all 7 integration tests pass with real API (post-migration to `google.genai`).

### E. Handoff documentation gaps

- **Test-baseline line inaccurate in prior prompts**: prompt-38.5 and 38.6 handoffs say measurement was `pytest tests/ -q --tb=no` but actually used `--ignore=tests/test_llama_cpp_adapter.py`. Fix: document `--ignore` as part of standard measurement command.
- **No "Devin memories not authoritative" landmine**: User deleted all Devin memories post-prompt-38.7. New policy: memories added only via explicit plan step. Any "per memory" citation is now a Rule 19 violation.
- **No "Integration tests" documentation**: Tests that require real services (LM Studio, API keys) should be documented in handoff "Test environment prerequisites" section.

### F. `requirements.txt` corrupted

Current `requirements.txt` has issues:
- `llama-cpp-python>=0.2.0` listed twice
- `pytest-asyncio>=0.23.0` line has weird spacing (corrupted)
- `icalendar>=5.0.0` line has weird spacing (corrupted)
- `google-generativeai>=0.3.0` needs to become `google-genai>=1.0.0`
- Missing `google-genai` (after migration)

## What to change

### Step 1 — Gemini SDK migration (no 20-line guard)

**File**: `adapters/gemini.py`

**Reference**: https://ai.google.dev/gemini-api/docs/sdks

**Key API changes**:
- `import google.generativeai as genai` → `from google import genai` + `from google.genai import types`
- `genai.configure(api_key=api_key)` → `client = genai.Client(api_key=api_key)` (hold as instance state)
- `genai.GenerativeModel(model_name)` → use `client` directly (model is a parameter to generate_content)
- `genai.types.GenerationConfig(...)` → `types.GenerateContentConfig(...)`
- **Async pattern**: `client.aio.models.generate_content(...)` for async
- **Streaming**: if adapter uses streaming, new SDK has different iterator shape — verify consumer code
- **`genai.types` namespace**: significantly restructured — check all type imports

**Remove the `# noqa: Plan 38.7` suppression** on line 12 — this plan executes the migration.

**Install the new package**:
```powershell
pip install google-genai
```

**Verify** (paste literal output into CHANGELOG per Rule 19):
```powershell
python -m pytest tests/test_gemini_adapter.py -v --tb=short
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12|FutureWarning"
```

First command: tests pass (after Step 4 mocks the client for unit tests; integration tests still skip without key). Second command: zero matches (warning eliminated).

### Step 2 — Fix `test_health_check_without_server` + add `test_health_check_with_server`

**File**: `tests/test_lm_studio_adapter.py`

**Fix `test_health_check_without_server`** (lines 60-66) — mock the HTTP client so the unit test is environment-independent:

```python
def test_health_check_without_server(self, lm_studio_adapter):
    """Test health check returns False when server not available (unit test, mocked)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock _client to raise on GET (simulating no server).
    # This makes the test environment-independent — passes regardless of
    # whether LM Studio is actually running.
    with patch.object(lm_studio_adapter, '_ensure_client'):
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        lm_studio_adapter._client = mock_client

        result = asyncio.run(lm_studio_adapter.health_check())
        assert result is False
```

**Add `test_health_check_with_server`** (NEW integration test) — verifies the happy path when LM Studio IS running:

```python
@pytest.mark.integration
def test_health_check_with_server(self, lm_studio_adapter):
    """Test health check returns True when LM Studio server is running (integration test).
    
    This test requires LM Studio to be running at http://localhost:1234/v1.
    Skip if not available — this is an integration test, not a unit test.
    """
    import asyncio
    import httpx

    # Check if LM Studio is actually running
    try:
        response = httpx.get(f"{lm_studio_adapter.base_url}/models", timeout=2.0)
        if response.status_code != 200:
            pytest.skip("LM Studio not running at http://localhost:1234/v1")
    except Exception:
        pytest.skip("LM Studio not running at http://localhost:1234/v1")

    # LM Studio is running — verify health_check returns True
    result = asyncio.run(lm_studio_adapter.health_check())
    assert result is True
```

The `@pytest.mark.integration` marker documents this as an integration test. The skip-if-not-running pattern means it skips gracefully in CI but runs when LM Studio is available.

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_lm_studio_adapter.py -v --tb=short
```

All tests pass:
- `test_health_check_without_server` PASSED (mocked — no real server needed)
- `test_health_check_with_server` PASSED (LM Studio running — see Step 5 verification)
- Other tests still pass

### Step 3 — Convert adapter unit tests to mocked

**Files**: `tests/test_anthropic_adapter.py`, `tests/test_gemini_adapter.py`

**Current pattern** (in both files): All tests use an `api_key` fixture that skips if env var not set. Even pure unit tests like `test_initialization` skip because the `adapter` fixture requires the key.

**Classification** (verified by reading test code):

| Test | Type | Action |
|---|---|---|
| `test_initialization` | Unit | Mock — run always |
| `test_model_name_property` | Unit | Mock — run always |
| `test_is_local_property` | Unit | Mock — run always |
| `test_cost_per_token_property` | Unit | Mock — run always |
| `test_health_check` | Integration | Keep env-conditional |
| `test_generate_simple_message` | Integration | Keep env-conditional |
| `test_generate_with_system_message` | Integration | Keep env-conditional |
| `test_generate_with_temperature` | Integration | Keep env-conditional |
| `test_generate_with_max_tokens` | Integration | Keep env-conditional |
| `test_close` | Unit (mostly) | Mock — run always (see note below) |
| `test_consecutive_generations` | Integration | Keep env-conditional |
| `test_generate_with_conversation_history` (Anthropic only) | Integration | Keep env-conditional |

**Note on `test_close`**: `AnthropicAdapter.__init__` sets `self._client = None` (lazy initialization — verified by reading `adapters/anthropic.py:44`). `close()` checks `if self._client:` — which is `None` initially, so `close()` does nothing if `_ensure_client()` was never called. The mock fixture patches `AsyncAnthropic` at the class level, but `_ensure_client()` is never called by `close()` itself. **The mocked `test_close` would pass trivially without testing anything** unless the fixture or test forces client creation first. Fix: in the `mock_adapter` fixture, call `mock_adapter._ensure_client()` after construction (or directly set `mock_adapter._client = mock_anthropic_client`) so `close()` has something to close. Same applies to Gemini's `mock_adapter` fixture (already shown above with `adapter._ensure_client()` call).

**Total per file**: 5 unit tests mocked + 7 integration tests env-conditional (Anthropic) / 5 unit + 6 integration (Gemini, which doesn't have `test_generate_with_conversation_history`).

**Fixed pattern** for `tests/test_anthropic_adapter.py`:

```python
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from adapters.anthropic import AnthropicAdapter
from core.schemas import Message, MessageRole
from core.worker_base import LLMResponse


# --- Mocked fixtures for unit tests (run always, no API key needed) ---

@pytest.fixture
def mock_anthropic_client():
    """Mock AsyncAnthropic client for unit tests."""
    with patch('adapters.anthropic.AsyncAnthropic') as mock_class:
        mock_instance = MagicMock()
        mock_instance.messages = MagicMock()
        mock_instance.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text="Mock response")],
            model="claude-sonnet-4-6",
            usage=MagicMock(input_tokens=10, output_tokens=5),
        ))
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_anthropic_client):
    """Anthropic adapter with mocked client — for unit tests."""
    adapter = AnthropicAdapter(api_key="mock-key", model_name="claude-sonnet-4-6")
    # Force eager client creation so test_close has something to close
    # (AnthropicAdapter.__init__ sets _client=None lazily; close() does
    # nothing if _client was never populated)
    adapter._ensure_client()
    return adapter


# --- Unit tests (mocked, run always) ---

class TestAnthropicAdapterUnit:
    """Unit tests for AnthropicAdapter — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        """Test adapter initialization."""
        assert mock_adapter.model_name == "claude-sonnet-4-6"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token == 0.003

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "claude-sonnet-4-6"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token == 0.003

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        """Test closing the adapter doesn't raise."""
        await mock_adapter.close()


# --- Integration tests (env-conditional, require real API key) ---

@pytest.fixture
def api_key():
    """Get Anthropic API key from environment."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY environment variable not set")
    return key


@pytest.fixture
def adapter(api_key):
    """Create Anthropic adapter with real API key — for integration tests."""
    return AnthropicAdapter(api_key=api_key)


class TestAnthropicAdapterIntegration:
    """Integration tests for AnthropicAdapter — require real ANTHROPIC_API_KEY."""

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Hello, how are you?", timestamp=datetime.now())]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model == "claude-sonnet-4-6"

    # ... (other integration tests, unchanged from current file)
```

**For `tests/test_gemini_adapter.py`**: Same pattern — mock `genai.Client` (post-migration) for unit tests. Keep integration tests env-conditional.

**Gemini mock fixture** (post-migration to `google.genai`):

```python
@pytest.fixture
def mock_genai_client():
    """Mock google.genai.Client for unit tests."""
    with patch('adapters.gemini.genai.Client') as mock_client_class:
        mock_client = MagicMock()
        # Mock the async generate_content path: client.aio.models.generate_content
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()
        mock_generate = AsyncMock(return_value=MagicMock(
            text="Mock response",
            usage_metadata=MagicMock(input_token_count=10, output_token_count=5),
        ))
        mock_client.aio.models.generate_content = mock_generate
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_adapter(mock_genai_client):
    """GeminiAdapter with mocked client — for unit tests."""
    from adapters.gemini import GeminiAdapter
    adapter = GeminiAdapter(api_key="mock-key", model_name="gemini-1.5-flash")
    # Force eager client creation so test_close has something to close
    adapter._ensure_client()
    return adapter
```

**Key points** for the Gemini mock:
- The new SDK uses `client.aio.models.generate_content(...)` for async — mock must expose this path
- Mock `text` attribute on response (new SDK returns `response.text`, not `response.content[0].text`)
- Mock `usage_metadata` with `input_token_count` / `output_token_count` (new SDK attribute names)
- Call `_ensure_client()` in the fixture so `test_close` has a mock client to close
- Verify the actual `GeminiAdapter` API surface post-migration matches the mock (adapt if Step 1's migration differs from what's documented)

**Verify per file** (paste literal output):
```powershell
python -m pytest tests/test_anthropic_adapter.py -v --tb=short
python -m pytest tests/test_gemini_adapter.py -v --tb=short
```

Expected:
- 5 unit tests PASSED (mocked, no key needed)
- 7-8 integration tests SKIPPED (no key set yet — will verify in Step 5)

### Step 4 — Verify trajectory_exporter skips still legitimate

**File**: `tests/test_trajectory_exporter.py`

**Action**: Read each skip. Verify:
1. Skip message references Plan 45 explicitly ✅
2. Plan 45 is still in the queue (check handoff deferred-actions)
3. Skip reason is still accurate (backend still doesn't support `fetch(Type, filter_func=...)`)

If all three hold: leave as-is. The 6 skips are legitimate Plan-N deferrals.

**Verify** (paste literal output):
```powershell
Select-String -Path tests\test_trajectory_exporter.py -Pattern "Plan 45" | Measure-Object -Line
```

Should return 6 (one per skip).

### Step 5 — End-to-end adapter verification (NON-NEGOTIABLE)

**This step verifies all 4 adapters actually work.** Do not skip. Do not defer. If an adapter can't be verified, document the specific failure and STOP.

#### Step 5a — Ollama verification

**Prerequisites**: Ollama installed and at least one model pulled (e.g., `ollama pull llama3`).

**Procedure**:
1. Verify Ollama is installed:
   ```powershell
   ollama --version
   ```
2. Start Ollama server (if not already running):
   ```powershell
   Start-Process ollama -ArgumentList "serve" -NoNewWindow
   Start-Sleep -Seconds 2
   ```
3. Run Ollama adapter tests:
   ```powershell
   python -m pytest tests/test_ollama_adapter.py -v --tb=short
   ```
4. If tests pass: paste literal output to CHANGELOG. Stop Ollama:
   ```powershell
   Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
   ```
5. If tests fail: paste literal output, investigate root cause.

**If Ollama not installed**: Install from https://ollama.com/download, then retry.

#### Step 5b — LM Studio verification

**Prerequisites**: LM Studio installed and a model loaded.

**Procedure**:
1. Verify LM Studio is running (per prior failure, it likely is):
   ```powershell
   curl http://localhost:1234/v1/models
   ```
2. Run LM Studio adapter tests (including new integration test from Step 2):
   ```powershell
   python -m pytest tests/test_lm_studio_adapter.py -v --tb=short
   ```
3. Both `test_health_check_without_server` (mocked) and `test_health_check_with_server` (integration) should pass.
4. Paste literal output to CHANGELOG.
5. If LM Studio not running: ask user to start it, then retry. Do NOT skip the integration test.

**If LM Studio not installed**: Install from https://lmstudio.ai/, load a model, start the local server, then retry.

#### Step 5c — Anthropic verification (API key required)

**Prerequisites**: `ANTHROPIC_API_KEY` env var set.

**Procedure**:
1. Check if `ANTHROPIC_API_KEY` is set:
   ```powershell
   if ($env:ANTHROPIC_API_KEY) { Write-Host "Key is set" } else { Write-Host "Key is NOT set" }
   ```
2. If not set: **STOP and use the API key request protocol** (see top of plan). Ask user with URL https://console.anthropic.com/settings/keys. Wait for user to paste key. Set as session env var.
3. Run Anthropic adapter integration tests:
   ```powershell
   python -m pytest tests/test_anthropic_adapter.py::TestAnthropicAdapterIntegration -v --tb=short
   ```
4. All 7 integration tests should pass with real API.
5. Paste literal output to CHANGELOG.
6. Clear the env var:
   ```powershell
   Remove-Item Env:\ANTHROPIC_API_KEY
   ```

**If API key invalid or rate-limited**: paste literal error, document in CHANGELOG. Don't mark as PASSED.

#### Step 5d — Gemini verification (API key required, post-migration)

**Prerequisites**: `GEMINI_API_KEY` env var set. `google-genai` package installed (Step 1).

**Procedure**:
1. Check if `GEMINI_API_KEY` is set:
   ```powershell
   if ($env:GEMINI_API_KEY) { Write-Host "Key is set" } else { Write-Host "Key is NOT set" }
   ```
2. If not set: **STOP and use the API key request protocol**. Ask user with URL https://aistudio.google.com/app/apikey. Wait for user to paste key. Set as session env var.
3. Run Gemini adapter integration tests:
   ```powershell
   python -m pytest tests/test_gemini_adapter.py::TestGeminiAdapterIntegration -v --tb=short
   ```
4. All 7 integration tests should pass with real API (post-migration).
5. Paste literal output to CHANGELOG.
6. Clear the env var:
   ```powershell
   Remove-Item Env:\GEMINI_API_KEY
   ```

**If API key invalid or migration broke tests**: paste literal error, investigate. Don't mark as PASSED.

#### Step 5e — Adapter verification summary

After all 4 adapters are verified, paste this summary to CHANGELOG:

```
#### Step 5 — Adapter verification summary

- Ollama: <PASSED / FAILED — explain>
- LM Studio: <PASSED / FAILED — explain>
- Anthropic: <PASSED / FAILED — explain>
- Gemini: <PASSED / FAILED — explain>

All adapters verified end-to-end against real services.
```

If any adapter FAILED: STOP. Do not proceed to Step 6. Report the failure to GLM.

### Step 6 — Clean up `requirements.txt`

**File**: `requirements.txt`

**Issues to fix**:
1. `llama-cpp-python>=0.2.0` listed twice — remove duplicate
2. `pytest-asyncio>=0.23.0` line has weird spacing — fix to clean line
3. `icalendar>=5.0.0` line has weird spacing — fix to clean line
4. `google-generativeai>=0.3.0` → `google-genai>=1.0.0` (per Step 1 migration)
5. Ensure all test dependencies are listed

**Verify**:
```powershell
Get-Content requirements.txt | Sort-Object | Get-Unique
# Should show no duplicates
pip install -r requirements.txt --dry-run
# Should run without errors
```

### Step 7 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Changes**:

1. **Add new landmine** to "Known landmines" section:

   > **Devin memories are not authoritative** (post-prompt-38.7 policy change). All Devin memories were deleted; new memories are added only when GLM/user explicitly requests via a plan step. Any plan or report that cites "per memory X" or "Mistake Pattern N" (where N is a Devin-memory concept, not a handoff recurring-mistake pattern) is a Rule 19 violation — the citation is unverifiable. All workarounds, methodologies, and constraints must live in the handoff or the plan itself.

2. **Update "Test environment prerequisites" section**:

   > **Standard test measurement command**: `python -m pytest tests/ -q --tb=no --ignore=tests/test_llama_cpp_adapter.py`
   >
   > The `--ignore=tests/test_llama_cpp_adapter.py` flag is required because `llama_cpp` is not installed in the development environment. The test file uses `pytest.importorskip("llama_cpp")` which should handle the missing dependency cleanly, but `--ignore` is used as belt-and-suspenders to ensure the test suite doesn't fail at collection time.
   >
   > **Integration tests**: Some tests require real services or API keys:
   > - `tests/test_lm_studio_adapter.py::test_health_check_with_server` — requires LM Studio running at http://localhost:1234/v1
   > - `tests/test_anthropic_adapter.py::TestAnthropicAdapterIntegration` — requires `ANTHROPIC_API_KEY` env var (get at https://console.anthropic.com/settings/keys)
   > - `tests/test_gemini_adapter.py::TestGeminiAdapterIntegration` — requires `GEMINI_API_KEY` env var (get at https://aistudio.google.com/app/apikey)
   >
   > Integration tests skip gracefully when prerequisites aren't available. Run them with prerequisites set to verify end-to-end behavior.

3. **Update "Last updated" line** to reference prompt-38.7.1.

4. **Update test baseline** in "What works right now" prose:
   > "1090 tests pass, 19 skipped (13 integration tests requiring API keys/services + 6 Plan 45 deferrals), 0 warnings."

5. **Remove Plan 38.7 from deferred-actions** (this plan executes the migration).

6. **Add "Adapter verification status" subsection** to "What works right now":
   > All 4 LLM adapters verified working end-to-end as of prompt-38.7.1:
   > - Ollama: ✅ verified
   > - LM Studio: ✅ verified
   > - Anthropic: ✅ verified (requires API key)
   > - Gemini: ✅ verified (requires API key, migrated to google.genai)

### Step 8 — Update CHANGELOG with literal evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence: Gemini migration diff stat, pytest output, warning count before/after
- Step 2 evidence: `test_lm_studio_adapter.py` pytest output (all tests pass, including new integration test)
- Step 3 evidence: `test_anthropic_adapter.py` and `test_gemini_adapter.py` pytest output (unit tests pass mocked, integration tests skip without key)
- Step 4 evidence: trajectory_exporter skip count verification
- Step 5 evidence: ALL 4 adapter verification outputs (Ollama, LM Studio, Anthropic, Gemini) — literal pytest output for each
- Step 6 evidence: `requirements.txt` before/after diff
- Final test counts: ~1090 passed, 19 skipped, 0 failed, 0 warnings

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-38.7..HEAD -- adapters/ tests/ scripts/ requirements.txt
```

**Expected**: empty output.

For handoff/CHANGELOG: allowed per known-landmine procedure.

### Gate 2 — Gemini warning eliminated

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12|FutureWarning"
```

**Expected**: zero matches.

### Gate 3 — `test_health_check_without_server` passes (mocked)

```powershell
python -m pytest tests/test_lm_studio_adapter.py::TestLMStudioAdapter::test_health_check_without_server -v --tb=short
```

**Expected**: PASSED.

### Gate 4 — All 4 adapters verified end-to-end

```powershell
Select-String -Path CHANGELOG.md -Pattern "Step 5 — Adapter verification summary"
```

**Expected**: 1 match. The summary must show all 4 adapters PASSED.

### Gate 5 — Skipped count reduced to ~19

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**: line contains `19 skipped` (13 integration + 6 Plan 45). Acceptable range: {18, 19, 20}.

### Gate 6 — Full clean baseline

```powershell
python -m pytest tests/ -q --tb=short --ignore=tests/test_llama_cpp_adapter.py
```

**Expected**:
- Passed: ~1090 (1080 + 10 mocked unit tests — 5 Anthropic + 5 Gemini)
- Skipped: ~19 (13 integration + 6 Plan 45)
- Failed: 0
- Warnings: 0

**Acceptable ranges**:
- Passed: {1087, 1088, 1089, 1090, 1091, 1092} — small variations OK
- Skipped: {18, 19, 20}
- Failed: {0}
- Warnings: {0}

Anything outside: STOP. Investigate.

### Gate 7 — `requirements.txt` clean

```powershell
# No duplicates
$lines = Get-Content requirements.txt | Where-Object { $_.Trim() -ne "" }
$duplicates = $lines | Group-Object | Where-Object { $_.Count -gt 1 }
$duplicates.Count
# Expected: 0

# No weird spacing
Select-String -Path requirements.txt -Pattern "^\s+\S" 
# Expected: zero matches (no leading whitespace on package lines)
```

### Gate 8 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Devin memories are not authoritative"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Standard test measurement command"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Adapter verification status"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "1090 tests pass"
```

**Expected**: at least 1 match for each.

### Gate 9 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-38.7.1
```

**Expected**: 1 match. **Do not skip this step.** (Known landmine from prompt-38.)

## STOP conditions

- **If Gemini migration surfaces unfixable test failures**: STOP. Paste literal traceback. May indicate the new SDK has breaking changes beyond what's documented.
- **If you find yourself about to skip Step 5 (adapter verification) for any reason**: STOP. Per the new "no interactive shell" landmine and this plan's intro, install/run/close services to verify adapters. Do not skip.
- **If API key request protocol isn't followed**: STOP. Do not silently skip integration tests. Ask the user for the key.
- **If any adapter fails end-to-end verification**: STOP. Do not proceed to Step 6. Report the failure to GLM.
- **If Gate 6 shows >20 skipped or >0 warnings**: STOP. Investigate which Step didn't achieve its expected reduction.
- **If Gate 9 shows no match**: push the tag, re-verify.
- **If you find yourself about to defer any step citing "per memory" or "Mistake Pattern N"**: STOP. Per new landmine (Step 7.1), Devin memories are not authoritative.

## Out of scope

- Broad-except audit (Plan 39+)
- ruff/mypy triage (Plans 43-44)
- trajectory_exporter functional redesign (Plan 45 — the 6 skips stay)
- `test_llama_cpp_adapter.py` — already handled via `--ignore` (documented in Step 7.2)
- Track B manual TUI verification (Track A from prompt-38.7 closed the Rule 19 violation)
- **Config file design for API keys** — adapters already accept `api_key` via constructor (correct pattern). Callers (tests) read from env vars. Handoff says SetupWizard writes `jarvis.config.yaml` + `.env` but this isn't implemented for cloud adapters. That's a real gap, but it's Plan 41+ territory (InputSanitiser wiring/redesign), not this plan. This plan uses env vars (current pattern) and documents the gap.

## Closing steps

1. `git add adapters/gemini.py tests/test_lm_studio_adapter.py tests/test_anthropic_adapter.py tests/test_gemini_adapter.py requirements.txt SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
2. `git commit -m "fix: prompt-38.7.1 — clean baseline + adapter verification (Gemini migration, LM Studio test fix, mocked unit tests, end-to-end adapter verification, requirements.txt cleanup)"`
3. `git tag prompt-38.7.1`
4. `git show prompt-38.7.1 --stat` — verify file list
5. `git rev-parse prompt-38.7.1` — confirm hash
6. Update `CHANGELOG.md` (append-only) with all step evidence per Rule 19
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" to reference prompt-38.7.1
   - Update test baseline to "~1090 passed, 19 skipped, 0 failed, 0 warnings"
   - Add "Devin memories are not authoritative" landmine (Step 7.1)
   - Update "Test environment prerequisites" with standard measurement command + integration tests documentation (Step 7.2)
   - Update "What works right now" prose count + add "Adapter verification status" subsection
   - Remove Plan 38.7 from deferred-actions
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-38.7.1 changelog and handoff update"`
10. `git push origin master && git push origin prompt-38.7.1`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.7.1` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 38.7.1 lands

**First fully clean baseline since prompt-37:**
- ~1090 passed
- ~19 skipped (13 integration tests + 6 Plan 45 deferrals)
- 0 failed
- 0 warnings

**All 4 LLM adapters verified working end-to-end:**
- Ollama ✅
- LM Studio ✅
- Anthropic ✅ (requires API key)
- Gemini ✅ (requires API key, migrated to google.genai)

The horizontal cleanup queue can now proceed with a clean foundation:

- **Plan 39** — Broad-except audit, part 2 (system/) — ~132 sites in resource_manager, model_acquisition, profiler, model_registry, monitor_daemon
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring (will also address config file design for API keys)
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45** — trajectory_exporter functional redesign (will eliminate the 6 remaining Plan 45 skips)

Plans 39+ can land in any order. The warnings/skipped/failure debt is cleared. All adapters are verified.

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan has 4 substantial scopes + adapter verification. Check that:

1. **The Gemini migration has no 20-line guard — is that the right call?** Plan 38.7 had the guard; this plan removes it because the plan's whole purpose is the migration. The guard caused three deferrals. Is removing it appropriate?

2. **The LM Studio test fix is correct?** Step 2 mocks `_ensure_client` and `_client` for the unit test. The new `test_health_check_with_server` integration test verifies the happy path against real LM Studio. Is this the right split between unit and integration testing?

3. **The adapter unit/integration test split is sound?** Step 3 classifies 4 tests as unit (mocked) and 7-8 as integration (env-conditional). Is the classification correct? Should `test_close` be mocked (it doesn't make a real API call but does need a real adapter instance)?

4. **The API key request protocol is clear?** The protocol at the top of the plan tells Devin to STOP, ask the user with a URL, wait for the key, set as session env var, run test, clear env var. Is this workable? Should the key be persisted to `.env` for future runs (no — security), or kept session-only (yes — current plan)?

5. **The end-to-end adapter verification (Step 5) is appropriately scoped?** Devin needs to install/run/close Ollama and LM Studio, and use the API key protocol for Anthropic and Gemini. Is this realistic for one plan execution? Should it be split into a separate verification plan?

6. **The `requirements.txt` cleanup is correct?** Step 6 fixes duplicates, spacing, and updates `google-generativeai` → `google-genai`. Is anything else needed (e.g., pinning versions, adding missing deps)?

7. **The "Devin memories not authoritative" landmine is clear?** Does it need examples of what counts as a "Devin-memory concept" vs a "handoff recurring-mistake pattern"?

8. **The config file design deferral is appropriate?** The plan defers config file design for API keys to Plan 41+. Is this the right call, or should this plan address it?

9. **No known landmines violated**:
   - Tag-push gate (closing step 11) ✅
   - Rule 19 evidence requirement (every step has literal output requirement) ✅
   - No `global_rules.md` citations ✅
   - No "per memory" citations (this plan ADDS the landmine against them) ✅
   - No re-guessing disproved hypotheses ✅
   - Drift check distinguishes code vs docs ✅
   - Test-count methodology documented (Step 7.2) ✅
   - "No interactive shell" landmine addressed — Step 5 explicitly requires install/run/close ✅

**Output format**: Lead with verdict (ship as-is / ship with a fix / send back), then list specific issues by severity. Skip praise. Cite specific line numbers when flagging factual errors.

**Token economy note**: Large plan (~700 lines). If round 1 finds only MINOR issues, apply and place directly. If CRITICAL, do round 2 diff review.
