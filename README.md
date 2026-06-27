# Sovereign AI

A sovereign AI agent system with memory, tool use, and multi-agent coordination.

## UI Shell

The web UI is a **vanilla JS** frontend served directly by FastAPI. No build step, no npm, no React, no TypeScript.

### Frontend (`web/static/`)

- **Stack**: Plain HTML + CSS + vanilla JavaScript (ES modules)
- **Layout**: 3-panel shell (sidebar / main pane / right panel) via CSS Grid
- **Terminal**: xterm.js loaded from CDN
- **Auth**: Bearer token in `Authorization` header (entered via modal on first load, persisted to `localStorage`)
- **Real-time**: WebSocket (`/ws/pty`) for terminal; polling for status/workers/approvals/costs/memory/logs
- **Files**: `index.html`, `style.css`, `api.js`, `ui.js`, `chat.js`, `models.js`, `workers.js`, `approvals.js`, `costs.js`, `memory.js`, `logs.js`

### Backend (`web/`)

- **Framework**: FastAPI
- **Static mount**: `app.mount("/", StaticFiles(directory="web/static", html=True))` — serves the frontend at the same origin as the API (no CORS issues)
- **Auth**: `AuthMiddleware` wraps all `/api/*` routes; bearer token validated against `AuthManager`
- **API**: 30+ endpoints under `/api/*` (status, workers, approvals, costs, memory, logs, models, debates, skills, sessions, system, resources, vram, trace, etc.)
- **Real-time**: `/ws/pty` WebSocket for terminal; SSE streams for reasoning/memory activations

### History

The original Next.js 15 + React + TypeScript + Tailwind v4 + Zustand frontend (Plans 80–95) was abandoned after three failed remediation rounds (Web GUI Fixes 1–3) due to persistent framework-level errors: hydration mismatches, TypeScript strict-mode breakage, PowerShell file corruption, xterm.js SSR crashes, and `useEffect` dependency issues. The vanilla JS rebuild (`web/static/`) shipped in commit `5de16ba` and was stabilized in `d8fb61a`. The old `src/` directory was removed in `c48ce4c` (tag `web-gui-rebuild-cleanup-1`). See `DECISIONS.md` Decision 11 and `LANDMINES.md` L23 for full context.

## Development

### Run the web UI

```bash
pip install -r txt/requirements.txt
python -m cli.main serve --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000/ in a browser
# Paste the auth token printed at startup into the modal
```

The same `:8000` port serves both the static frontend (`/`) and the API (`/api/*`). No separate frontend dev server is needed.

### Run the CLI / TUI

```bash
python -m cli.main          # Rich CLI
python -m cli.main tui      # Textual TUI
```

### Running Tests

Python (pytest):

```bash
python -m pytest tests/ -q --tb=short
```

Static analysis:

## Architecture

See DECISIONS.md for detailed architectural decisions.

## License

MIT
