# Plan 40: Remaining cloud adapter test coverage (Mistral, Together, DeepSeek, HuggingFace)

> **Executor instructions**: This plan writes test files for the last 4 cloud LLM adapters (mistral, together, deepseek, huggingface), registers them in `cli/adapter_factory.py`, and verifies them end-to-end. After this plan, 10 of 14 adapters have test coverage and are registered in the factory.
>
> **Key design insight**: 3 of 4 adapters (mistral, together, deepseek) use `AsyncOpenAI` with a custom `base_url` — they're OpenAI-compatible APIs. Same mock pattern as OpenAI/Groq from Plan 39. HuggingFace uses `httpx.AsyncClient` directly (different mock pattern, similar to LM Studio).
>
> **Critical**: Use the API key request protocol (top of plan) for each adapter. Do NOT silently skip integration tests. Do NOT defer adapter verification citing "no service available."
>
> **Scope discipline**: Do NOT update production adapter files unless explicitly required by this plan. If tests reveal a deprecated model name or other production issue, STOP and report — do not make unilateral fixes (per new landmine from prompt-39 review).
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-39..HEAD -- adapters/ tests/ cli/adapter_factory.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `adapters/`, `tests/`, `cli/adapter_factory.py`: expected empty. For handoff/CHANGELOG: allowed per known-landmine procedure.

## Status

- **Priority**: P1 (complete adapter test coverage)
- **Effort**: M (4 new test files + adapter_factory update + 4 adapter verifications)
- **Risk**: LOW (3 of 4 adapters follow established OpenAI-compatible pattern; HuggingFace uses httpx pattern from LM Studio)
- **Depends on**: prompt-39 (commit `b4ee989`, tag `prompt-39`)
- **Planned at**: master HEAD post-prompt-39, 2026-06-19
- **In scope**:
  - Tests: `tests/test_mistral_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_together_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_deepseek_adapter.py` (NEW — 5 unit + 6 integration)
  - Tests: `tests/test_huggingface_adapter.py` (NEW — 5 unit + 6 integration)
  - Production: `cli/adapter_factory.py` (register mistral, together, deepseek, huggingface)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update adapter verification status, test baseline, TUI slash commands)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: mcp_adapter (special-purpose, separate plan), llama_cpp (working as intended per user), broad-except audit (Plan 41+), ruff/mypy triage, **production adapter code changes** (if tests reveal deprecated models or other issues, STOP and report — do not unilaterally update)

## Why this matters

After Plan 39, 6 of 14 adapters have test coverage and are registered in `cli/adapter_factory.py`. This plan completes the cloud adapter subset (10 of 14 total), leaving only:
- `llama_cpp.py` (working as intended, `--ignore`d in standard measurement)
- `mcp_adapter.py` (special-purpose, separate plan)
- `base.py` (base class, not an adapter)

**Bonus**: Registering these 4 adapters in `cli/adapter_factory.py` means `/adapter mistral`, `/adapter together`, `/adapter deepseek`, `/adapter huggingface` will actually work in the TUI — closing the handoff's documented bug ("the other 9 listed adapters crash with ValueError"). After this plan, only 4 of 14 adapters remain unregistered (llama_cpp, mcp, base — all special-purpose).

**Expected outcome**: ~1124 passed (1104 + 20 new mocked unit tests), ~61 skipped (37 existing + 24 new integration), 0 failed, 0 warnings. Plus 4 more adapters verified end-to-end (or documented as code-correct-blocked-by-external-issue).

## API key request protocol (for Devin)

When a test requires an API key that isn't set in the environment:

1. **STOP.** Do not skip silently. Do not defer.
2. **Report to user with the appropriate URL**:
   - Mistral: `"Test requires MISTRAL_API_KEY. Get one at: https://console.mistral.ai/api-keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - Together: `"Test requires TOGETHER_API_KEY. Get one at: https://api.together.xyz/settings/api-keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - DeepSeek: `"Test requires DEEPSEEK_API_KEY. Get one at: https://platform.deepseek.com/api_keys. Paste the key in chat and I'll set it as a session env var for this test run only."`
   - HuggingFace: `"Test requires HUGGINGFACE_API_KEY (or HF_TOKEN). Get one at: https://huggingface.co/settings/tokens. Paste the key in chat and I'll set it as a session env var for this test run only."`
3. **Wait for user to paste the key.**
4. **Set as session env var** (PowerShell `$env:VAR = "..."`). Do NOT write to file. Do NOT commit. Do NOT echo.
5. **Run the test.** Paste literal pass/fail output.
6. **Clear the env var**: `Remove-Item Env:\VAR`

## What's broken

### A. 4 cloud adapters have no test files

| Adapter | Test file | SDK client | API pattern |
|---|---|---|---|
| `adapters/mistral.py` | (none) | `AsyncOpenAI` with `base_url="https://api.mistral.ai/v1"` | OpenAI-compatible |
| `adapters/together.py` | (none) | `AsyncOpenAI` with `base_url="https://api.together.xyz/v1"` | OpenAI-compatible |
| `adapters/deepseek.py` | (none) | `AsyncOpenAI` with `base_url="https://api.deepseek.com/v1"` | OpenAI-compatible |
| `adapters/huggingface.py` | (none) | `httpx.AsyncClient` with `Authorization: Bearer <key>` header | Custom HTTP |

The 3 OpenAI-compatible adapters (mistral, together, deepseek) use the **exact same mock pattern** as OpenAI/Groq from Plan 39 — mock `AsyncOpenAI` class, configure `chat.completions.create` to return mock response with `choices[0].message.content`.

HuggingFace uses `httpx.AsyncClient` directly (like LM Studio). Mock pattern: patch `httpx.AsyncClient` or set `_client` directly with a mock that returns mock HTTP responses.

### B. `cli/adapter_factory.py` doesn't register these 4 adapters

Current factory registers 6 adapters (ollama, lm_studio, openai, cohere, groq, anthropic — per prompt-39). Need to add `elif` branches for `mistral`, `together`, `deepseek`, `huggingface`.

## What to change

### Step 1 — Write `tests/test_mistral_adapter.py`

**File**: `tests/test_mistral_adapter.py` (NEW)

Follow the OpenAI-compatible pattern from Plan 39. Mistral uses `AsyncOpenAI` with a custom `base_url`, but the response shape is identical to OpenAI.

**Mock fixture** (same pattern as OpenAI/Groq):
```python
@pytest.fixture
def mock_mistral_client():
    """Mock AsyncOpenAI client for Mistral unit tests.
    
    Mistral uses AsyncOpenAI with base_url="https://api.mistral.ai/v1" —
    OpenAI-compatible response shape (choices[0].message.content).
    """
    with patch('adapters.mistral.AsyncOpenAI') as mock_class:
        mock_instance = MagicMock()
        mock_instance.chat = MagicMock()
        mock_instance.chat.completions = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mock response"))],
            model="mistral-large-latest",
            usage=MagicMock(prompt_tokens=10, completion_tokens=5),
        ))
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_mistral_client):
    """MistralAdapter with mocked client — for unit tests."""
    from adapters.mistral import MistralAdapter
    adapter = MistralAdapter(api_key="mock-key", model_name="mistral-large-latest")
    adapter._ensure_client()
    return adapter


class TestMistralAdapterUnit:
    """Unit tests — mocked, no API key required."""

    def test_initialization(self, mock_adapter):
        assert mock_adapter.model_name == "mistral-large-latest"
        assert mock_adapter.is_local is False
        assert mock_adapter.cost_per_token > 0

    def test_model_name_property(self, mock_adapter):
        assert mock_adapter.model_name == "mistral-large-latest"

    def test_is_local_property(self, mock_adapter):
        assert mock_adapter.is_local is False

    def test_cost_per_token_property(self, mock_adapter):
        assert mock_adapter.cost_per_token > 0

    @pytest.mark.asyncio
    async def test_close(self, mock_adapter):
        await mock_adapter.close()


class TestMistralAdapterIntegration:
    """Integration tests — require real MISTRAL_API_KEY."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        if not os.getenv("MISTRAL_API_KEY"):
            pytest.skip("MISTRAL_API_KEY environment variable not set")

    @pytest.fixture
    def adapter(self):
        from adapters.mistral import MistralAdapter
        return MistralAdapter(api_key=os.getenv("MISTRAL_API_KEY"), model_name="mistral-large-latest")

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        is_healthy = await adapter.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_generate_simple_message(self, adapter):
        messages = [Message(role=MessageRole.USER, content="Hello", timestamp=datetime.now())]
        response = await adapter.generate(messages)
        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, adapter):
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful.", timestamp=datetime.now()),
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
        messages = [Message(role=MessageRole.USER, content="Tell me a story.", timestamp=datetime.now())]
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
python -m pytest tests/test_mistral_adapter.py -v --tb=short
```

Expected: 5 unit tests PASSED (mocked), 6 integration tests SKIPPED (no key set yet).

### Step 2 — Write `tests/test_together_adapter.py`

**File**: `tests/test_together_adapter.py` (NEW)

Same OpenAI-compatible pattern. Together uses `AsyncOpenAI` with `base_url="https://api.together.xyz/v1"`. Default model: `mistralai/Mixtral-8x7B-Instruct-v0.1`.

**Copy Step 1's fixture and test classes verbatim**, then apply these substitutions:

- Patch target: `adapters.mistral.AsyncOpenAI` → `adapters.together.AsyncOpenAI`
- Adapter class: `MistralAdapter` → `TogetherAdapter`
- Module import: `from adapters.mistral import MistralAdapter` → `from adapters.together import TogetherAdapter`
- Env var: `MISTRAL_API_KEY` → `TOGETHER_API_KEY`
- Default model name (in fixture, unit test assertions, and integration test construction): `"mistral-large-latest"` → `"mistralai/Mixtral-8x7B-Instruct-v0.1"`
- Class names: `TestMistralAdapterUnit` → `TestTogetherAdapterUnit`, `TestMistralAdapterIntegration` → `TestTogetherAdapterIntegration`
- Fixture names: `mock_mistral_client` → `mock_together_client`

**MANDATORY**: Read `adapters/together.py:generate()` to confirm response shape matches OpenAI (it should, since it's OpenAI-compatible). If response shape differs, adapt the mock.

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_together_adapter.py -v --tb=short
```

### Step 3 — Write `tests/test_deepseek_adapter.py`

**File**: `tests/test_deepseek_adapter.py` (NEW)

Same OpenAI-compatible pattern. DeepSeek uses `AsyncOpenAI` with `base_url="https://api.deepseek.com/v1"`. Default model: `deepseek-chat`.

**Copy Step 1's fixture and test classes verbatim**, then apply these substitutions:

- Patch target: `adapters.mistral.AsyncOpenAI` → `adapters.deepseek.AsyncOpenAI`
- Adapter class: `MistralAdapter` → `DeepSeekAdapter`
- Module import: `from adapters.mistral import MistralAdapter` → `from adapters.deepseek import DeepSeekAdapter`
- Env var: `MISTRAL_API_KEY` → `DEEPSEEK_API_KEY`
- Default model name (in fixture, unit test assertions, and integration test construction): `"mistral-large-latest"` → `"deepseek-chat"`
- Class names: `TestMistralAdapterUnit` → `TestDeepSeekAdapterUnit`, `TestMistralAdapterIntegration` → `TestDeepSeekAdapterIntegration`
- Fixture names: `mock_mistral_client` → `mock_deepseek_client`

**MANDATORY**: Read `adapters/deepseek.py:generate()` to confirm response shape matches OpenAI (it should, since it's OpenAI-compatible). If response shape differs, adapt the mock.

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_deepseek_adapter.py -v --tb=short
```

### Step 4 — Write `tests/test_huggingface_adapter.py`

**File**: `tests/test_huggingface_adapter.py` (NEW)

**Different pattern** — HuggingFace uses `httpx.AsyncClient` directly (not an SDK client class). Mock pattern is similar to LM Studio from Plan 38.7.1.

**MANDATORY**: Before writing the mock, read `adapters/huggingface.py:generate()` AND `adapters/huggingface.py:health_check()` to confirm:
1. What HTTP endpoint `generate()` calls (likely `POST {base_url}/{model_name}`)
2. What request body shape `generate()` sends
3. What response shape `generate()` expects (likely JSON array like `[{"generated_text": "..."}]`)
4. **What `health_check()` does** — does it call GET, POST, or is it implemented without a real HTTP call (e.g., returns True unconditionally if api_key is set)? The mock must cover whatever `health_check()` actually does, or `test_health_check` will fail with `AttributeError` or hit the real network.

**Mock fixture** (provisional — verify against adapter code, including health_check()):
```python
@pytest.fixture
def mock_hf_client():
    """Mock httpx.AsyncClient for HuggingFace unit tests.
    
    PROVISIONAL SHAPE — read adapters/huggingface.py:generate() and adapt
    the mock to match the actual HTTP request/response shape the adapter
    consumes. HuggingFace Inference API typically returns:
    [{"generated_text": "..."}] for text-generation models.
    """
    mock_instance = MagicMock()
    # Mock POST response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{"generated_text": "Mock response"}])
    mock_response.raise_for_status = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_instance.get = AsyncMock(return_value=mock_response)
    mock_instance.aclose = AsyncMock()
    
    with patch('adapters.huggingface.httpx.AsyncClient') as mock_class:
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_adapter(mock_hf_client):
    """HuggingFaceAdapter with mocked client — for unit tests."""
    from adapters.huggingface import HuggingFaceAdapter
    adapter = HuggingFaceAdapter(api_key="mock-key", model_name="meta-llama/Meta-Llama-3-70B-Instruct")
    adapter._ensure_client()
    return adapter
```

**Unit tests + Integration tests**: Same structure as other adapters (5 unit + 6 integration).

**Verify** (paste literal output):
```powershell
python -m pytest tests/test_huggingface_adapter.py -v --tb=short
```

### Step 5 — Update `cli/adapter_factory.py`

**File**: `cli/adapter_factory.py`

Add `elif` branches for `mistral`, `together`, `deepseek`, `huggingface`. Same pattern as prompt-39's openai/cohere/groq/anthropic branches.

```python
    elif adapter_name_lower == "mistral":
        from adapters.mistral import MistralAdapter
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set")
        return MistralAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "together":
        from adapters.together import TogetherAdapter
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("TOGETHER_API_KEY environment variable not set")
        return TogetherAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "deepseek":
        from adapters.deepseek import DeepSeekAdapter
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        return DeepSeekAdapter(api_key=api_key, model_name=model_name)
    elif adapter_name_lower == "huggingface":
        from adapters.huggingface import HuggingFaceAdapter
        api_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        if not api_key:
            raise ValueError("HUGGINGFACE_API_KEY (or HF_TOKEN) environment variable not set")
        return HuggingFaceAdapter(api_key=api_key, model_name=model_name)
    else:
        available = ["ollama", "lm_studio", "openai", "cohere", "groq", "anthropic", "mistral", "together", "deepseek", "huggingface"]
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available adapters: {', '.join(available)}"
        )
```

Note: HuggingFace accepts either `HUGGINGFACE_API_KEY` or `HF_TOKEN` (the standard HuggingFace env var name). The factory checks both.

**Verify** (paste literal output):
```powershell
# Verify factory constructs each adapter (with mock env vars)
$env:MISTRAL_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('mistral', 'mistral-large-latest'); print(type(a).__name__)"; Remove-Item Env:\MISTRAL_API_KEY
$env:TOGETHER_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('together', 'mistralai/Mixtral-8x7B-Instruct-v0.1'); print(type(a).__name__)"; Remove-Item Env:\TOGETHER_API_KEY
$env:DEEPSEEK_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('deepseek', 'deepseek-chat'); print(type(a).__name__)"; Remove-Item Env:\DEEPSEEK_API_KEY
$env:HUGGINGFACE_API_KEY = "test"; python -c "from cli.adapter_factory import create_adapter; a = create_adapter('huggingface', 'meta-llama/Meta-Llama-3-70B-Instruct'); print(type(a).__name__)"; Remove-Item Env:\HUGGINGFACE_API_KEY
```

Expected: prints `MistralAdapter`, `TogetherAdapter`, `DeepSeekAdapter`, `HuggingFaceAdapter`.

### Step 6 — End-to-end adapter verification (NON-NEGOTIABLE)

For each of the 4 adapters, verify integration tests pass with real API key. Use the API key request protocol at the top of the plan.

#### Step 6a — Mistral verification

1. Check if `MISTRAL_API_KEY` is set. If not, use API key request protocol with URL https://console.mistral.ai/api-keys.
2. Run: `python -m pytest tests/test_mistral_adapter.py::TestMistralAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

#### Step 6b — Together verification

1. Check if `TOGETHER_API_KEY` is set. If not, use API key request protocol with URL https://api.together.xyz/settings/api-keys.
2. Run: `python -m pytest tests/test_together_adapter.py::TestTogetherAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

#### Step 6c — DeepSeek verification

1. Check if `DEEPSEEK_API_KEY` is set. If not, use API key request protocol with URL https://platform.deepseek.com/api_keys.
2. Run: `python -m pytest tests/test_deepseek_adapter.py::TestDeepSeekAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

#### Step 6d — HuggingFace verification

1. Check if `HUGGINGFACE_API_KEY` (or `HF_TOKEN`) is set. If not, use API key request protocol with URL https://huggingface.co/settings/tokens.
2. Run: `python -m pytest tests/test_huggingface_adapter.py::TestHuggingFaceAdapterIntegration -v --tb=short`
3. Paste literal output to CHANGELOG.
4. Clear env var.

**If any adapter fails** (billing, service outage, deprecated model): paste literal error, document in CHANGELOG. Don't mark as PASSED. Note: external billing/service issues are not Rule 19 violations if documented properly.

**If tests reveal a deprecated model name or other production code issue**: STOP. Do NOT unilaterally update the adapter (per new landmine from prompt-39 review). Report the issue to GLM/user. A follow-up plan can address the production code change with proper review.

#### Step 6e — Adapter verification summary

```
#### Step 6 — Adapter verification summary

- Mistral: <PASSED / FAILED — explain>
- Together: <PASSED / FAILED — explain>
- DeepSeek: <PASSED / FAILED — explain>
- HuggingFace: <PASSED / FAILED — explain>
```

### Step 7 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

1. Update "Last updated" to reference prompt-40.
2. Update test baseline: `~1124 passed, ~61 skipped, 0 failed, 0 warnings`.
3. Update "Adapter verification status" subsection:
   > 10 of 14 LLM adapters have test coverage as of prompt-40:
   > - Ollama: ✅ verified (prompt-38.7)
   > - LM Studio: ✅ verified (prompt-38.7.1)
   > - Groq: ✅ verified (prompt-39)
   > - Mistral: <✅/⚠️> (prompt-40)
   > - Together: <✅/⚠️> (prompt-40)
   > - DeepSeek: <✅/⚠️> (prompt-40)
   > - HuggingFace: <✅/⚠️> (prompt-40)
   > - OpenAI: ⚠️ code correct, blocked by quota (prompt-39)
   > - Cohere: ⚠️ code correct, blocked by deprecated models (prompt-39)
   > - Anthropic: ⚠️ code correct, blocked by credit balance (prompt-38.7.1)
   > - Gemini: ⚠️ code correct, blocked by service outage (prompt-38.7.1)
   > - Remaining 3 (llama_cpp, mcp_adapter, base): special-purpose or working as intended
4. Update TUI slash commands documentation:
   > **TUI slash commands** — `/adapter` now supports 10 adapters: ollama, lm_studio, openai, cohere, groq, anthropic, mistral, together, deepseek, huggingface. Remaining 4 (llama_cpp, mcp, base) are special-purpose.
5. Update "Test environment prerequisites" with new integration tests + URLs.
6. Update "Next 5 prompts" to reflect broad-except audit (Plan 41) as next in queue.

### Step 8 — Update CHANGELOG with literal evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence: `test_mistral_adapter.py` pytest output
- Step 2 evidence: `test_together_adapter.py` pytest output
- Step 3 evidence: `test_deepseek_adapter.py` pytest output
- Step 4 evidence: `test_huggingface_adapter.py` pytest output (including the MANDATORY adapter code verification per Step 4 instructions)
- Step 5 evidence: `adapter_factory.py` diff + factory construct verification output
- Step 6 evidence: ALL 4 adapter verification outputs — literal pytest output for each
- Final test counts: ~1124 passed, ~61 skipped, 0 failed, 0 warnings

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-39..HEAD -- adapters/ tests/ cli/adapter_factory.py
```

**Expected**: empty output.

### Gate 2 — 4 new test files exist and unit tests pass

```powershell
Test-Path tests/test_mistral_adapter.py
Test-Path tests/test_together_adapter.py
Test-Path tests/test_deepseek_adapter.py
Test-Path tests/test_huggingface_adapter.py
python -m pytest tests/test_mistral_adapter.py tests/test_together_adapter.py tests/test_deepseek_adapter.py tests/test_huggingface_adapter.py -v --tb=short
```

**Expected**: `True` for all four Test-Path. Pytest shows 20 unit tests PASSED (5 each), 24 integration tests SKIPPED (6 each).

### Gate 3 — `adapter_factory.py` registers 10 adapters

```powershell
Select-String -Path cli\adapter_factory.py -Pattern "mistral|together|deepseek|huggingface"
```

**Expected**: at least 4 matches (one `elif` branch per adapter).

### Gate 4 — All 4 adapters verified end-to-end (or documented as blocked)

```powershell
Select-String -Path CHANGELOG.md -Pattern "Step 6 — Adapter verification summary"
```

**Expected**: 1 match. Summary shows all 4 adapters with verdict (PASSED or ⚠️ with explanation).

### Gate 5 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short --ignore=tests/test_llama_cpp_adapter.py
```

**Expected**:
- Passed: ~1124 (1104 + 20 new mocked unit tests)
- Skipped: ~61 (37 existing + 24 new integration)
- Failed: 0
- Warnings: 0

**Acceptable ranges**:
- Passed: {1120, 1121, 1122, 1123, 1124, 1125, 1126}
- Skipped: {60, 61, 62}
- Failed: {0}
- Warnings: {0}

### Gate 6 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "1124 tests pass"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "10 of 14 LLM adapters"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "10 adapters"
```

**Expected**: at least 1 match each.

### Gate 7 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-40
```

**Expected**: 1 match. **Do not skip this step.**

## STOP conditions

- **If you find yourself about to skip Step 6 (adapter verification) for any reason**: STOP. Use the API key request protocol.
- **If API key request protocol isn't followed**: STOP. Do not silently skip integration tests.
- **If tests reveal a deprecated model name or other production code issue**: STOP. Do NOT unilaterally update the adapter (per new landmine from prompt-39 review). Report the issue to GLM/user. A follow-up plan can address production code changes with proper review.
- **If any adapter fails end-to-end verification due to code issue** (not external billing/service): STOP. Investigate the root cause.
- **If adapter fails due to external issue** (billing, service outage, deprecated model): document the specific error, mark as ⚠️ in handoff, proceed.
- **If Gate 5 shows >62 skipped or >0 warnings**: STOP. Investigate.
- **If Gate 7 shows no match**: push the tag, re-verify.

## Out of scope

- mcp_adapter (special-purpose, separate plan)
- llama_cpp (working as intended per user; `--ignore` is belt-and-suspenders)
- base.py (base class, not an adapter)
- broad-except audit (Plan 41+)
- ruff/mypy triage
- **Production adapter code changes** (if tests reveal issues, STOP and report — do not unilaterally fix)
- Re-verification of blocked adapters from prompt-39 (OpenAI/Cohere/Anthropic/Gemini — those remain ⚠️ until external issues resolve)

## Closing steps

1. `git add tests/test_mistral_adapter.py tests/test_together_adapter.py tests/test_deepseek_adapter.py tests/test_huggingface_adapter.py cli/adapter_factory.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
2. `git commit -m "fix: prompt-40 — Mistral/Together/DeepSeek/HuggingFace adapter test coverage + adapter_factory registration"`
3. `git tag prompt-40`
4. `git show prompt-40 --stat` — verify file list
5. `git rev-parse prompt-40` — confirm hash
6. Update `CHANGELOG.md` (append-only) with all step evidence per Rule 19
7. Update `SOVEREIGN_AI_HANDOFF.md` per Step 7
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-40 changelog and handoff update"`
10. `git push origin master && git push origin prompt-40`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-40` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 40 lands

**10 of 14 adapters have test coverage and are registered in `cli/adapter_factory.py`:**
- Ollama, LM Studio, Groq, Mistral, Together, DeepSeek, HuggingFace — verified ✅ (or ⚠️ blocked by external)
- OpenAI, Cohere, Anthropic, Gemini — ⚠️ code correct, blocked by external issues (billing/service/deprecated models)

**TUI `/adapter` command** supports 10 adapters (up from 6 in prompt-39, up from 2 pre-prompt-39).

**Remaining adapter work**:
- mcp_adapter (special-purpose, separate plan)
- llama_cpp (working as intended)
- base.py (base class)

**Then horizontal cleanup queue**:
- **Plan 41** — Broad-except audit, part 1 (core/) — addresses TUI `/adapter` ValueError handling that Plan 39's comment referenced
- Plan 42 — Broad-except audit, part 2 (system/)
- Plan 43 — Broad-except audit, part 3 (skills/)
- Plan 44 — InputSanitiser wiring
- Plan 45 — InputSanitiser redesign
- Plan 46 — ruff triage
- Plan 47 — mypy triage
- Plan 48+ — trajectory_exporter redesign, graphify integration, marine stack

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan writes 4 new test files + updates adapter_factory + verifies 4 adapters. Check that:

1. **Is the OpenAI-compatible pattern correctly applied to Mistral/Together/DeepSeek?** All 3 use `AsyncOpenAI` with custom `base_url`. The mock pattern from Plan 39 (mock `AsyncOpenAI`, configure `chat.completions.create`) should work identically. Is this correct?

2. **Is the HuggingFace mock pattern correct?** HuggingFace uses `httpx.AsyncClient` directly (not an SDK class). The mock patches `httpx.AsyncClient` and configures `post`/`get` to return mock responses. The response shape (`[{"generated_text": "..."}]`) is provisional — the plan includes MANDATORY instruction to verify against `adapters/huggingface.py:generate()`. Is this the right approach?

3. **Is the adapter_factory HuggingFace env var check correct?** HuggingFace accepts either `HUGGINGFACE_API_KEY` or `HF_TOKEN` (standard HF env var). The factory checks both. Is this the right pattern?

4. **Is the scope-discipline STOP condition clear?** Per new landmine from prompt-39 review, if tests reveal deprecated models or other production issues, Devin should STOP and report — not unilaterally fix. Is this STOP condition explicit enough?

5. **Is the test count math correct?** 1104 + 20 new unit tests (5×4) = 1124. 37 existing skipped + 24 new (6×4) = 61 skipped. Does this match Gate 5?

6. **No known landmines violated**:
   - Tag-push gate (closing step 11) ✅
   - Rule 19 evidence requirement ✅
   - No `global_rules.md` citations ✅
   - No "per memory" citations ✅
   - No re-guessing disproved hypotheses ✅
   - Drift check distinguishes code vs docs ✅
   - Test-count methodology documented ✅
   - "No interactive shell" landmine addressed via API key request protocol ✅
   - **NEW: Scope creep via "necessary" model updates** (prompt-39 had this) — Step 6 STOP condition explicitly forbids unilateral production code changes ✅
