# Sovereign AI

A sovereign AI agent system with memory, tool use, and multi-agent coordination.

## UI Shell (Plan 80)

This repository includes a Next.js + FastAPI UI shell for visualizing agent state.

### Frontend (src/)

- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript 5 (strict mode)
- **Styling**: Tailwind CSS v4 with custom design tokens
- **State**: Zustand 4.5
- **Components**: shadcn/ui (copy-paste, no runtime dependency)

### Backend (backend/)

- **Framework**: FastAPI
- **Auth**: Cookie-based with Bearer header fallback
- **Streaming**: Server-Sent Events (SSE) for real-time updates
- **Data**: In-memory mocks (real orchestrator integration deferred)

## Development

### Frontend

`ash
cd src
npm install
npm run dev    # http://localhost:3000
npm run build
npm run test   # Vitest
npm run lint   # ESLint
`

### Backend

`ash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload  # http://localhost:8000
`

Set environment variable:
`ash
export SOVEREIGN_DEV_TOKEN=dev-token-sovereign-ai-ui
`

### Running Tests

Frontend (Vitest):
`ash
cd src
npm run test
`

Backend (pytest):
`ash
python -m pytest tests/test_ui_backend.py -q --tb=short
`

## Architecture

See DECISIONS.md for detailed architectural decisions.

## License

MIT
