# Plan 39: OpenAI-compatible adapter test coverage + Anthropic re-verification

> **Executor instructions**: This plan writes test files for 3 cloud LLM adapters (OpenAI, Cohere, Groq), re-verifies Anthropic (which failed in prompt-38.7.1 due to insufficient credit balance), and registers all 4 adapters in `cli/adapter_factory.py` so `/adapter <name>` works in the TUI.
>
> **Critical**: Use the API key request protocol (top of plan) for each adapter that needs a key. Do NOT silently skip integration tests. Do NOT defer adapter verification citing "no service available" — get the API key from the user, run the test, paste literal output.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-38.7.1..HEAD -- adapters/ tests/ cli/adapter_factory.py requirements.txt SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `adapters/`, `tests/`, `cli/adapter_factory.py`, `requirements.txt`: expected empty. For handoff/CHANGELOG: allowed per known-landmine procedure.

## Status

- **Priority**: P1 (adapter test coverage + TUI adapter command wiring)
- **Effort**: M (3 new test files + adapter_factory update + 4 adapter verifications)
- **Risk**: LOW (test files follow established pattern from prompt-38.7.1; adapter_factory update is mechanical)
- **Depends on**: prompt-38.7.1 (commit `a9d6baa`, tag `prompt-38.7.1`)
- **Planned at**: master HEAD post-prompt-38.7.1, 2026-06-19
- **In scope**:
  - Tests: `tests/test_openai_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_cohere_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_groq_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_anthropic_adapter.py` (verify integration tests pass now that user may have topped up credits)
  - Production: `cli/adapter_factory.py` (register openai, cohere, groq, anthropic — currently only ollama and lm_studio)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update adapter verification status, update test baseline, update TUI slash commands documentation)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: mistral/together/deepseek/huggingface (Plan 40), llama_cpp (working as intended per user — `--ignore` is just belt-and-suspenders), mcp_adapter (special-purpose, separate plan), broad-except audit (Plan 41+), ruff/mypy triage

## Why this matters

The framework has 14 adapter files in `adapters/`, but:
- Only 4 have test files (ollama, lm_studio, anthropic, gemini)
- Only 2 are registered in `cli/adapter_factory.py` (ollama, lm_studio)
- The TUI's `/adapter` command crashes with `ValueError` for the other 12

This plan addresses the OpenAI-compatible subset (OpenAI, Cohere, Groq) plus re-verifies Anthropic. After this plan, 6 of 14 adapters will have test coverage and be registered in the factory. Plan 40 will handle the remaining cloud adapters (Mistral, Together, DeepSeek, HuggingFace).

**Bonus**: Registering these 4 adapters in `cli/adapter_factory.py` means `/adapter openai`, `/adapter cohere`, `/adapter groq`, `/adapter anthropic` will actually work in the TUI — closing one of the handoff's documented bugs ("the other 9 listed adapters crash with ValueError").

**Expected outcome**: ~1104 passed (1089 + 15 new mocked unit tests), ~37 skipped (13 existing integration + 18 new integration + 6 Plan 45), 0 failed, 0 warnings. Plus 6 of 14 adapters verified end-to-end.

## API key request protocol (for Devin)

When a test requires an API key that isn't set in the environment:

1. **STOP.** Do not skip silently. Do not defer.
2. **Report to user with the appropriate URL**:
   - OpenAI: `"Test requires OPENAI_API_KEY. Get one at: https://platform.openai.com/api-keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - Cohere: `"Test requires COHERE_API_KEY. Get one at: https://dashboard.cohere.com/api-keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - Groq: `"Test requires GROQ_API_KEY. Get one at: https://console.groq.com/keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - Anthropic: `"Test requires ANTHROPIC_API_KEY. Get one at: https://console.anthropic.com/settings/keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
3. **Wait for user to paste the key.**
4. **Set as session env var** (PowerShell `$env:VAR = "..."`). Do NOT write to file. Do NOT commit. Do NOT echo.
5. **Run the test.** Paste literal pass/fail output.
6. **Clear the env var**: `Remove-Item Env:\VAR`

## What's broken

### A. 3 cloud adapters have no test files

| Adapter | Test file | Status |
|---|---|---|
| `adapters/openai.py` | `tests/test_openai_adapter.py` | Does not exist |
| `adapters/cohere.py` | `tests/test_cohere_adapter.py` | Does not exist |
| `adapters/groq.py` | `tests/test_groq_adapter.py` | Does not exist |

All 3 adapters follow the same pattern as `adapters/anthropic.py` (lazy `_ensure_client`, `close()` checks `if self._client:`). The mock pattern from prompt-38.7.1 translates directly.

### B. Anthropic verification failed in prompt-38.7.1

Anthropic integration tests failed with "insufficient credit balance" — API key was valid but account had no credits. User may have topped up credits since then. Re-verify in this plan.

### C. `cli/adapter_factory.py` only registers 2 of 14 adapters

Current `create_adapter()` function:
```python
if adapter_name_lower == "ollama":
    ...
elif adapter_name_lower == "lm_studio":
    ...
else:
    available = ["ollama", "lm_studio"]
    raise ValueError(f"Unknown adapter: {adapter_name}. Available adapters: {', '.join(available)}")
```

Need to add `elif` branches for `openai`, `cohere`, `groq`, `anthropic`. Each constructs the adapter with `api_key` from env var (since these are cloud adapters, the key must come from environment, not hardcoded).

## What to change

### Step 1 — Write `tests/test_openai_adapter.py`

**File**: `tests/test_openai_adapter.py` (NEW)

Follow the pattern from `tests/test_anthropic_adapter.py` (post-prompt-38.7.1). 5 unit tests (mocked) + 6 integration tests (env-conditional).

**Mock fixture** (mocks `AsyncOpenAI`):
```python
@pytest.fixture
def mock_openai_client():
    """Mock AsyncOpenAI client for unit tests."""
    with patch('adapters.openai.AsyncOpenAI') as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat = MagicMock()
        mock_instance.chat.completions = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mock response"))],
            model="gpt-4",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5),
        ))
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_openai_client):
    """OpenAIAdapter with mocked client — for unit tests."""
    from adapters.openai import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="mock-key", model_name="gpt-4")
    # Force eager client creation so test_close has something to close
    adapter._ensure_client()
    return adapter


class TestOpenAIAdapterUnit:
    """Unit tests — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        assert mock_adapter.model_name == "gpt-4"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token > 0  # Check actual value in adapter

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "gpt-4"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token > 0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        await mock_adapter.close()
        # Should not raise


class TestOpenAIAdapterIntegration:
    """Integration tests — require real OPENAI_API_KEY."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY environment variable not set")

    @pytest.fixture
    def adapter(self):
        from adapters.openai import OpenAIAdapter
        return OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY"), model_name="gpt-4")

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

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, adapter):
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are a helpful assistant.", timestamp=datetime.now()),
            Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now()),
        ]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Say something creative.", timestamp=datetime.now())]
        response = await adapter.generate(messages, temperature=0.8)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Tell me a short story.", timestamp=datetime.now())]
        response = await adapter.generate(messages, max_tokens=100)
        assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_consecutive_generations(self, adapter):
        messages1 = [Message(role=MessageRole.USER, content="What is 1+1?", timestamp=datetime.now())]
        messages2 = [Message(role=MessageRole.USER, content="What is 2+2?", timestamp=datetime.now())]
        response1 = await adapter.generate(messages1)
        response2 = await adapter.generate(messages2)
        assert isinstance(response1, LLMResponse)
        assert isinstance(response2, LLMResponse)
```

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_openai_adapter.py -v --tb=short
```

Expected: 5 unit tests PASSED (mocked), 6 integration tests SKIPPED (no key set yet — will verify in Step 5).

### Step 2 — Write `tests/test_cohere_adapter.py`

**File**: `tests/test_cohere_adapter.py` (NEW)

Same pattern. Mock `cohere.AsyncClient`. Note: Cohere's chat API uses a different response shape than OpenAI — verify by reading `adapters/cohere.py:generate()` method. The mock should match whatever the adapter actually consumes.

**Mock fixture** (adapt based on actual Cohere response shape):
```python
@pytest.fixture
def mock_cohere_client():
    """Mock cohere.AsyncClient for unit tests.
    
    PROVISIONAL SHAPE — read adapters/cohere.py:generate() and adapt the mock
    to match the actual response attributes the adapter consumes before
    running tests. The current Cohere Python SDK (cohere>=5.x) uses
    client.chat() as a top-level async call returning a NonStreamedChatResponse
    where text is in response.message.content[0].text (NOT response.text) and
    usage is in response.usage.billed_units.input_tokens / output_tokens.
    The mock below uses the older response.text shape — verify and update.
    """
    with patch('adapters.cohere.cohere.AsyncClient') as mock_class:
        mock_instance = MagicMock()
        # Cohere v5+ SDK: client.chat() is a top-level async method, not chat.completions.create
        mock_instance.chat = AsyncMock(return_value=MagicMock(
            # Likely correct shape (verify against adapter code):
            message=MagicMock(content=[MagicMock(text="Mock response")]),
            usage=MagicMock(billed_units=MagicMock(input_tokens=10, output_tokens=5)),
            # Fallback attributes in case adapter uses older API:
            text="Mock response",
            meta=MagicMock(tokens=MagicMock(input_tokens=10, output_tokens=5)),
        ))
        mock_class.return_value = mock_instance
        yield mock_instance
```

**MANDATORY**: Before running Cohere tests, read `adapters/cohere.py:generate()` and confirm which response attributes the adapter actually consumes. Update the mock to match — do NOT treat the fixture above as authoritative. If the adapter uses `response.message.content[0].text`, ensure the mock provides that path. If it uses `response.text`, the fallback attribute covers it. Paste the actual response shape from the adapter code into the CHANGELOG as evidence.

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_cohere_adapter.py -v --tb=short
```

### Step 3 — Write `tests/test_groq_adapter.py`

**File**: `tests/test_groq_adapter.py` (NEW)

Same pattern. Mock `AsyncGroq`. Groq uses OpenAI-compatible response shape (since it's an OpenAI-compatible API).

**Mock fixture**:
```python
@pytest.fixture
def mock_groq_client():
    """Mock AsyncGroq client for unit tests."""
    with patch('adapters.groq.AsyncGroq') as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat = MagicMock()
        mock_instance.chat.completions = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mock response"))],
            model="llama3-70b-8192",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5),
        ))
        mock_class.return_value = mock_instance
        yield mock_instance
```

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_groq_adapter.py -v --tb=short
```

### Step 4 — Update `cli/adapter_factory.py`

**File**: `cli/adapter_factory.py`

Add `elif` branches for `openai`, `cohere`, `groq`, `anthropic`. Each constructs the adapter with `api_key` from env var.

```python
def create_adapter(
    adapter_name: str,
    model_name: str,
    base_url: str | None = None,
) -> LLMAdapter:
    import os
    adapter_name_lower = adapter_name.lower()

    # NOTE: Cloud adapters (openai, cohere, groq, anthropic) raise ValueError
    # if their API key env var is not set. The TUI's /adapter command (caller)
    # should catch this ValueError and display a user-friendly message like
    # "OPENAI_API_KEY not set — get one at https://platform.openai.com/api-keys"
    # instead of crashing with a traceback. This TUI-level handler is deferred
    # to Plan 41 (broad-except audit will address the /adapter call site).
    # See handoff "What's broken" section for the /adapter ValueError bug.

    if adapter_name_lower == "ollama":
        from adapters.ollama import OllamaAdapter
        return OllamaAdapter(
            base_url=base_url or "http://localhost:11434",
            model_name=model_name,
        )
    elif adapter_name_lower == "lm_studio":
        from adapters.lm_studio import LMStudioAdapter
        return LMStudioAdapter(
            base_url=base_url or "http://localhost:1234",
            model_name=model_name,
        )
    elif adapter_name_lower == "openai":
        from adapters.openai import OpenAIAdapter
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return OpenAIAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "cohere":
        from adapters.cohere import CohereAdapter
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY environment variable not set")
        return CohereAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "groq":
        from adapters.groq import GroqAdapter
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        return GroqAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "anthropic":
        from adapters.anthropic import AnthropicAdapter
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return AnthropicAdapter(api_key=api_key, model_name=model_name)
    else:
        available = ["ollama", "lm_studio", "openai", "cohere", "groq", "anthropic"]
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available adapters: {', '.join(available)}"
        )
```

**Verify** (paste literal output):
```powershell
# Verify factory constructs each adapter (with mock env vars)
$env:OPENAI_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('openai', 'gpt-4'); print(type(a).__name__)"; Remove-Item Env:\OPENAI_API_KEY
$env:COHERE_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('cohere', 'command-r-plus'); print(type(a).__name__)"; Remove-Item Env:\COHERE_API_KEY
$env:GROQ_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('groq', 'llama3-70b-8192'); print(type(a).__name__)"; Remove-Item Env:\GROQ_API_KEY
$env:ANTHROPIC_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('anthropic', 'claude-sonnet-4-6'); print(type(a).__name__)"; Remove-Item Env:\ANTHROPIC_API_KEY
```

Expected: prints `OpenAIAdapter`, `CohereAdapter`, `GroqAdapter`, `AnthropicAdapter`.

### Step 5 — End-to-end adapter verification (NON-NEGOTIABLE)

For each of the 4 adapters, verify integration tests pass with real API key. Use the API key request protocol at the top of the plan.

#### Step 5a — OpenAI verification

1. Check if `OPENAI_API_KEY` is set. If not, use API key request protocol with URL https://platform.openai.com/api-keys.
2. Run: `python -m pytest tests/test_openai_adapter.py::TestOpenAIAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var: `Remove-Item Env:\OPENAI_API_KEY`

#### Step 5b — Cohere verification

1. Check if `COHERE_API_KEY` is set. If not, use API key request protocol with URL https://dashboard.cohere.com/api-keys.
2. Run: `python -m pytest tests/test_cohere_adapter.py::TestCohereAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

#### Step 5c — Groq verification

1. Check if `GROQ_API_KEY` is set. If not, use API key request protocol with URL https://console.groq.com/keys.
2. Run: `python -m pytest tests/test_groq_adapter.py::TestGroqAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

#### Step 5d — Anthropic re-verification

1. Check if `ANTHROPIC_API_KEY` is set. If not, use API key request protocol with URL https://console.anthropic.com/settings/keys.
2. Run: `python -m pytest tests/test_anthropic_adapter.py::TestAnthropicAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

**If any adapter fails** (e.g., Anthropic still has insufficient credits): paste literal error, document in CHANGELOG. Don't mark as PASSED. Note: external billing/service issues are not Rule 19 violations if documented properly.

#### Step 5e — Adapter verification summary

```
#### Step 5 — Adapter verification summary

- OpenAI: <PASSED / FAILED — explain>
- Cohere: <PASSED / FAILED — explain>
- Groq: <PASSED / FAILED — explain>
- Anthropic: <PASSED / FAILED — explain> (re-verification from prompt-38.7.1)
```

### Step 6 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

1. Update "Last updated" to reference prompt-39.
2. Update test baseline: `~1104 passed, ~37 skipped, 0 failed, 0 warnings`.
3. Update "Adapter verification status" subsection:
   > All 6 of 14 LLM adapters verified working end-to-end as of prompt-39:
   > - Ollama: ✅ verified (prompt-38.7)
   > - LM Studio: ✅ verified (prompt-38.7.1)
   > - OpenAI: ✅ verified (prompt-39)
   > - Cohere: ✅ verified (prompt-39)
   > - Groq: ✅ verified (prompt-39)
   > - Anthropic: ✅ verified (prompt-39, re-verified from prompt-38.7.1)
   > - Gemini: ⚠️ code correct, runtime verification blocked by external service issue (prompt-38.7.1)
   > - Remaining 7 adapters (mistral, together, deepseek, huggingface, llama_cpp, mcp, base): Plan 40+
4. Update TUI slash commands documentation in "What works right now":
   > **TUI slash commands** — `/help`, `/status`, `/clear`, `/exit`, `/model`, `/adapter`, `/theme` work. `/adapter` now supports: ollama, lm_studio, openai, cohere, groq, anthropic (6 adapters). Remaining 8 adapters still need factory registration (Plan 40+).
5. Update "Test environment prerequisites" with new integration tests + URLs.
6. Update "Next 5 prompts" to reflect Plan 40 (remaining cloud adapters) as next in queue.

### Step 7 — Update CHANGELOG with literal evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence: `test_openai_adapter.py` pytest output (5 unit PASSED, 6 integration SKIPPED)
- Step 2 evidence: `test_cohere_adapter.py` pytest output
- Step 3 evidence: `test_groq_adapter.py` pytest output
- Step 4 evidence: `adapter_factory.py` diff + factory construct verification output
- Step 5 evidence: ALL 4 adapter verification outputs (OpenAI, Cohere, Groq, Anthropic) — literal pytest output for each
- Final test counts: ~1104 passed, ~37 skipped, 0 failed, 0 warnings

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-38.7.1..HEAD -- adapters/ tests/ cli/adapter_factory.py requirements.txt
```

**Expected**: empty output.

### Gate 2 — 3 new test files exist and unit tests pass

```powershell
Test-Path tests/test_openai_adapter.py
Test-Path tests/test_cohere_adapter.py
Test-Path tests/test_groq_adapter.py
python -m pytest tests/test_openai_adapter.py tests/test_cohere_adapter.py tests/test_groq_adapter.py -v --tb=short
```

**Expected**: `True` for all three Test-Path. Pytest shows 15 unit tests PASSED (5 each), 18 integration tests SKIPPED (6 each).

### Gate 3 — `adapter_factory.py` registers 6 adapters

```powershell
Select-String -Path cli\adapter_factory.py -Pattern "openai|cohere|groq|anthropic"
```

**Expected**: at least 4 matches (one `elif` branch per adapter).

### Gate 4 — All 4 adapters verified end-to-end

```powershell
Select-String -Path CHANGELOG.md -Pattern "Step 5 — Adapter verification summary"
```

**Expected**: 1 match. Summary shows all 4 adapters with verdict.

### Gate 5 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short --ignore=tests/test_llama_cpp_adapter.py
```

**Expected**:
- Passed: ~1104 (1089 + 15 new mocked unit tests)
- Skipped: ~37 (13 existing integration + 18 new integration + 6 Plan 45)
- Failed: 0
- Warnings: 0

**Acceptable ranges**:
- Passed: {1100, 1101, 1102, 1103, 1104, 1105, 1106}
- Skipped: {36, 37, 38}
- Failed: {0}
- Warnings: {0}

### Gate 6 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "1104 tests pass"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "6 of 14 LLM adapters verified"
```

**Expected**: at least 1 match each.

### Gate 7 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-39
```

**Expected**: 1 match. **Do not skip this step.**

## STOP conditions

- **If you find yourself about to skip Step 5 (adapter verification) for any reason**: STOP. Use the API key request protocol. Do not silently skip.
- **If API key request protocol isn't followed**: STOP. Do not silently skip integration tests.
- **If any adapter fails end-to-end verification due to code issue** (not external billing/service): STOP. Investigate the root cause. Document in CHANGELOG.
- **If adapter fails due to external issue** (billing, service outage): document the specific error, mark as ⚠️ in handoff, proceed. External failures are not Rule 19 violations if documented.
- **If Gate 5 shows >38 skipped or >0 warnings**: STOP. Investigate.
- **If Gate 7 shows no match**: push the tag, re-verify.

## Out of scope

- mistral/together/deepseek/huggingface adapters (Plan 40)
- llama_cpp adapter (working as intended per user; `--ignore` is belt-and-suspenders)
- mcp_adapter (special-purpose, separate plan)
- broad-except audit (Plan 41+)
- ruff/mypy triage
- Removing `--ignore=tests/test_llama_cpp_adapter.py` (deferred — would need to verify `importorskip` works without it)

## Closing steps

1. `git add tests/test_openai_adapter.py tests/test_cohere_adapter.py tests/test_groq_adapter.py cli/adapter_factory.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
2. `git commit -m "fix: prompt-39 — OpenAI/Cohere/Groq adapter test coverage + Anthropic re-verification + adapter_factory registration"`
3. `git tag prompt-39`
4. `git show prompt-39 --stat` — verify file list
5. `git rev-parse prompt-39` — confirm hash
6. Update `CHANGELOG.md` (append-only) with all step evidence per Rule 19
7. Update `SOVEREIGN_AI_HANDOFF.md` per Step 6
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-39 changelog and handoff update"`
10. `git push origin master && git push origin prompt-39`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-39` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 39 lands

**6 of 14 adapters verified working end-to-end:**
- Ollama ✅
- LM Studio ✅
- OpenAI ✅
- Cohere ✅
- Groq ✅
- Anthropic ✅ (or ⚠️ if still billing-blocked)

**Test baseline**: ~1104 passed, ~37 skipped, 0 failed, 0 warnings.

**TUI `/adapter` command** now supports 6 adapters (up from 2).

**Remaining adapter work** (Plan 40+):
- Plan 40: mistral, together, deepseek, huggingface (4 cloud adapters)
- Plan 41+: mcp_adapter (special-purpose)
- Optional: remove `--ignore=tests/test_llama_cpp_adapter.py` if `importorskip` works without it

**Then horizontal cleanup queue**:
- Broad-except audit (was Plan 39 in old numbering, now Plan 41+)
- ruff triage
- mypy triage
- trajectory_exporter redesign (Plan 45)

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan writes 3 new test files + updates adapter_factory + re-verifies Anthropic. Check that:

1. **The mock patterns are correct for each adapter?** OpenAI uses `AsyncOpenAI` with `chat.completions.create`. Cohere uses `cohere.AsyncClient` with `chat` (different response shape). Groq uses `AsyncGroq` (OpenAI-compatible). Are the mock fixtures correctly differentiated?

2. **The adapter_factory update handles missing API keys correctly?** Cloud adapters need `api_key` from env var. The plan raises `ValueError` if env var not set. Is this the right error handling, or should it skip more gracefully?

3. **The test count math is correct?** 1089 + 15 new unit tests = 1104. 13 existing integration + 18 new (6×3) = 31 integration + 6 Plan 45 = 37 skipped. Does this match Gate 5?

4. **The Anthropic re-verification is appropriate?** It failed in prompt-38.7.1 due to billing. Re-verifying in this plan is reasonable if user has topped up credits. Should the plan check credit balance before running tests, or just run them and let failures surface naturally?

5. **No known landmines violated**:
   - Tag-push gate (closing step 11) ✅
   - Rule 19 evidence requirement ✅
   - No `global_rules.md` citations ✅
   - No "per memory" citations ✅
   - No re-guessing disproved hypotheses ✅
   - Drift check distinguishes code vs docs ✅
   - Test-count methodology documented ✅
   - "No interactive shell" landmine addressed via Step 5 install/run/verify ✅
