# Skill Plugin Specification

## Overview
This document defines the specification for skill plugins in the Sovereign AI Agent Framework. Skills are modular capabilities that can be dynamically discovered and loaded by the Skill Registry.

## SKILL.md Format
Every skill must include a `SKILL.md` file in its directory that declares the following metadata:

### Required Fields

#### Skill Name and Description
- **name**: Human-readable name of the skill
- **description**: Detailed description of what the skill does

#### Input Parameters
- **parameters**: List of input parameters with:
  - Parameter name
  - Type (str, int, float, bool, list, dict, etc.)
  - Whether the parameter is required or optional
  - Default value (if optional)
  - Description of what the parameter controls

#### Output Format
- **output**: Description of the output format
- **return_type**: Python type annotation for the return value

#### External Dependencies
- **dependencies**: List of external services or adapters required
  - Examples: httpx, BeautifulSoup, specific adapters
  - Must specify version constraints if applicable

#### Hardware Requirements
- **hardware**: Hardware requirements, if any
  - Examples: minimum RAM, GPU requirements
  - Leave empty if no special hardware needed

#### Task Suitability Tags
- **tags**: List of tags describing when this skill is suitable
  - Examples: web-scraping, file-io, data-processing
  - Used by orchestrator for skill selection

## Example SKILL.md

```markdown
# Web Scraper Skill

## Description
Scrapes webpage content using HTTP requests and HTML parsing.

## Parameters
- url (str, required): The URL to scrape
- selector (str, optional): CSS selector for targeted scraping

## Output
Returns scraped text content as a string.

## Dependencies
- httpx>=0.24.0
- beautifulsoup4>=4.12.0

## Hardware
No special hardware requirements.

## Tags
web-scraping, data-extraction, http
```

## Skill Implementation Requirements

### Python Module
Each skill must implement a `skill.py` file with:

1. **Async execution**: All skill functions must be async
2. **Type annotations**: All public functions must have return type annotations
3. **Error handling**: Must handle errors gracefully and raise appropriate exceptions
4. **No global state**: Skills must be stateless or use constructor-injected state

### Constructor Signature
```python
def __init__(self, emitter: TraceEmitter | None = None) -> None:
    self.emitter = emitter or NullTraceEmitter()
```

### Main Execution Method
```python
async def execute(self, **kwargs) -> Any:
    # Implementation
    pass
```

## Skill Registry Integration

Skills are discovered by the Skill Registry by:
1. Scanning the `skills/` directory for subdirectories containing `SKILL.md`
2. Parsing each `SKILL.md` to extract metadata
3. Validating the skill against this specification
4. Registering the skill with its metadata for query by capability, task type, or dependency

## Clean Architecture Compliance

Skills must comply with Clean Architecture:
- Skills can import from `core/` only
- Skills must not import from `adapters/`, `workers/`, `cli/`, or `memory/`
- Skills must not import from other skills
- All I/O operations must be async
- Skills must emit TraceEvents via injected emitter
