# System Prompt — Sovereign AI Interface (GLM Build Brief)

> Hand this entire document to GLM as a system prompt or first user message.
> It gives GLM the architectural context, feature targets, design language,
> and implementation constraints needed to build a Sovereign AI UI that is
> *inspired by* — but meaningfully distinct from — Hermes Agent.

---

## 1. Project identity

You are building **Sovereign AI** — a self-hosted, sovereign-first AI agent
interface. The product philosophy is:

- **Ownership over convenience.** The user controls all data, models, and
  memory. Nothing leaves their machine without explicit approval.
- **Transparency over magic.** Every agent action — tool calls, memory writes,
  reasoning steps — is visible and inspectable in real time.
- **Composable over monolithic.** The UI is a shell of independent panels that
  can be added, removed, or rearranged. No panel is required for the others to
  function.

The visual language is **dark, dense, and purposeful** — not decorative
cyberpunk. Think: mission-critical dashboards, not gaming aesthetics. Amber and
slate are the primary accent colors. Monospace is used for all agent output;
a clean sans-serif is used for chrome.

---

## 2. Tech stack (required)

| Layer | Technology |
|---|---|
| Framework | **Next.js 15** (App Router, `src/app/`) |
| Language | **TypeScript 5** — strict mode, no `any` |
| UI primitives | **shadcn/ui** (New York variant) |
| Styling | **Tailwind CSS v4** |
| State | **Zustand 5** (one store per domain: agent, memory, tools, sessions) |
| Animation | **Framer Motion** (layout animations only — no decorative loops) |
| Terminal embed | **xterm.js** (`@xterm/xterm` + `@xterm/addon-fit` + WebGL renderer) |
| Charts | **Recharts** (for token/latency/confidence panels) |
| Icons | **Lucide React** |
| Runtime | **Bun** |
| Backend | **FastAPI** (Python 3.11) served via Uvicorn, WebSocket for streaming |
| Database | **SQLite** via **Prisma** (sessions, memory slots, tool call log) |

Do not introduce libraries outside this list without noting the addition and
its justification in a `DECISIONS.md` file.

---

## 3. Core features to implement

Implement each feature independently as a self-contained panel component.
Panels are composed into the shell layout — they do not depend on each other.

### 3.1 Agent status bar (top of shell)

A slim, always-visible top bar. Contains:

- **Session ID** — short hash, e.g. `SES-8f2a`, copyable on click
- **Phase badge** — one of `Sovereign · Planning`, `Sovereign · Acting`,
  `Sovereign · Reflecting`, `Sovereign · Idle`. Badge background shifts:
  slate for idle, amber for planning, emerald for acting, violet for reflecting.
  Color transitions use a 300ms ease.
- **Model slug** — e.g. `GLM-4.5 Flash` — clickable to open the model picker
  modal
- **Latency chip** — live ms counter, updated on each agent turn
- **Run/Pause toggle** — single button, keyboard shortcut `Space`
- **Settings gear** — opens the global settings drawer

*Do not implement this as a fixed/sticky element — use normal document flow
with `position: sticky top-0 z-50` so it scrolls with the page only at the
very top.*

### 3.2 Activation grid panel

A Canvas 2D panel showing agent memory slot activations as a dot matrix.

Spec:
- **32 columns × 16 rows** of cells (512 total, matching a 512-slot memory
  store)
- Each cell maps to one memory slot. Activation level `[0, 1]` controls:
  - Cell size (low activation = small dot; full activation = filled square)
  - Color: `0–0.4` → slate, `0.4–0.7` → amber, `0.7–1.0` → emerald
- Cells decay by `−0.015` per animation frame when not explicitly written
- Clicking a cell opens an inline tooltip showing the slot index, last written
  timestamp, key, and a truncated value preview
- The panel has a compact legend bar beneath: `● Inactive  ● Recall  ● Write`
- Real activations come from the `/api/memory/activations` SSE stream;
  simulate with random decay/write if the backend is not connected

*Use `requestAnimationFrame` for the animation loop. Draw to a `<canvas>` with
`devicePixelRatio` scaling. Do not use WebGL for this panel — Canvas 2D is
sufficient and keeps the bundle small.*

### 3.3 Tool call inspector panel

A live, scrollable log of tool invocations. Each entry is an expandable card.

Card anatomy:
- **Status indicator** — pulsing blue dot for in-flight, solid green for
  success, amber for warning, red for error
- **Tool name** — monospace, e.g. `web_search`, `memory_write`, `code_exec`
- **Duration chip** — ms elapsed, right-aligned
- **Expand/collapse** — click anywhere on the header row
- **Expanded body:**
  - Arguments rendered as a two-column key/value grid (key: muted, value:
    monospace code pill)
  - Output block: monospace pre-formatted, max-height 160px with internal
    scroll, syntax-highlighted if JSON
  - Latency bar: proportional fill, color-coded (green < 200ms, amber
    200–500ms, red > 500ms)
- New entries animate in from the top (slide-down, 200ms)
- Maximum 50 entries retained; older entries are evicted from the bottom

*Tool call events come from the `/api/tools/stream` SSE endpoint (
`data: {"id": "...", "tool": "...", "status": "running", "args": {...}}`).
Updates to an existing call patch by `id` — they do not create a new entry.*

### 3.4 Session timeline panel

A horizontal Gantt-style timeline of agent phase segments for the current
session.

Spec:
- Four tracks, one per phase: Planning / Acting / Reflecting / Error
- Each segment is a rounded rect whose width is proportional to duration
- Segment opacity encodes confidence: `opacity = 0.25 + confidence * 0.75`
- Hover tooltip: phase label, start time, duration, confidence, tool count
- Click a segment to jump the tool call inspector to that time slice
- A vertical "now" cursor auto-advances in real time
- Zoom slider `0.5×–4×` stretches the time axis
- Summary stat row beneath: total elapsed, avg confidence, tool calls, steps

*Render as SVG. Use a `useTimeline` hook that takes an array of
`{phase, startMs, durationMs, confidence}` objects and returns layout rects.*

### 3.5 Reasoning / thought stream panel

A live text panel that shows the agent's chain-of-thought as it streams.

Spec:
- Renders token-by-token via SSE (`/api/agent/reasoning`)
- Text is monospace, small (12px), muted color — clearly secondary to the
  main response
- A collapsible header: `▶ Reasoning  (243 tokens)` — collapsed by default,
  expands on click
- When collapsed, shows only the last line of reasoning as a one-line preview
- A "Copy reasoning" button appears on hover of the expanded block
- Reasoning from previous turns is kept but visually dimmed (`opacity: 0.4`)

### 3.6 Memory inspector drawer

A slide-in drawer (from the right, 480px wide) listing all memory slots.

Spec:
- Table view: columns = Slot #, Key, Value preview (truncated to 60 chars),
  Last written, Activation level (mini bar)
- Sortable by each column
- Search/filter bar at the top (`/` to focus)
- Clicking a row expands it to show the full value and a "Clear slot" button
- A "Export memory" button downloads `memory.json`
- An "Import memory" button opens a file picker and writes slots via
  `POST /api/memory/import`
- The drawer is opened from a `Memory` button in the status bar or via
  keyboard shortcut `M`

### 3.7 Subagent spawner panel

A panel showing active subagents (isolated agent processes delegated a
sub-task).

Each subagent card shows:
- Subagent ID and assigned task description (truncated)
- Status: `Running`, `Waiting`, `Complete`, `Failed`
- A mini activation grid (8×4) showing that subagent's memory state
- Token cost so far
- A `Kill` button (with confirmation) that terminates the subagent process

*Subagent state comes from `/api/subagents` polled every 2 seconds. The mini
grid does not animate — it updates on each poll.*

---

## 4. Layout shell

```
┌─────────────────────────────────────────────────────────┐
│  Status bar (sticky top)                                │
├──────────┬──────────────────────────────┬───────────────┤
│ Sidebar  │  Main: Terminal / Chat pane  │  Right panel  │
│ nav      │  (xterm.js embed)            │  (inspector,  │
│ (64px)   │                              │  timeline,    │
│          │                              │  reasoning)   │
├──────────┴──────────────────────────────┴───────────────┤
│  Bottom bar: Activation grid + token counter            │
└─────────────────────────────────────────────────────────┘
```

- Sidebar: icon-only by default, expands to 200px on hover. Icons: Terminal,
  Memory, Subagents, Tools, Settings, Help.
- Right panel: tab-switcher between Tool Inspector, Timeline, and Reasoning.
- Bottom bar: always visible, contains the 32×16 activation grid on the left
  and a token usage counter + context bar on the right.
- The terminal pane takes all remaining space. xterm.js fills it via
  `@xterm/addon-fit` on `ResizeObserver`.

Use CSS Grid for the shell — no absolute positioning except the sticky status
bar and the memory drawer overlay.

---

## 5. Backend API contract

The FastAPI backend must expose these endpoints. Implement stubs if needed.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Agent phase, session ID, uptime, model slug |
| `GET` (SSE) | `/api/agent/reasoning` | Streaming reasoning tokens |
| `GET` (SSE) | `/api/tools/stream` | Tool call events (create + patch) |
| `GET` (SSE) | `/api/memory/activations` | Memory slot activation deltas |
| `GET` | `/api/memory/slots` | All slots (paginated, sortable) |
| `POST` | `/api/memory/import` | Bulk import slots from JSON |
| `DELETE` | `/api/memory/slots/{id}` | Clear one slot |
| `GET` | `/api/sessions` | Session list with metadata |
| `GET` | `/api/sessions/{id}/timeline` | Phase segments for timeline |
| `GET` | `/api/subagents` | Active subagent list |
| `DELETE` | `/api/subagents/{id}` | Kill a subagent |
| `WS` | `/api/pty` | Bidirectional PTY stream for xterm.js |

All SSE endpoints use `Content-Type: text/event-stream` with
`data: <JSON>\n\n` framing. All REST endpoints return `application/json`.
Auth is a bearer token passed as `Authorization: Bearer <token>` — generate a
random 32-byte hex token on first launch and write it to `~/.sovereign/token`.

---

## 6. Design constraints

### Color tokens (Tailwind v4 CSS vars — define in `src/app/globals.css`)

```css
:root {
  --color-surface-base:    #0c0c0f;   /* page background */
  --color-surface-raised:  #13131a;   /* cards, panels */
  --color-surface-overlay: #1a1a24;   /* modals, drawers */
  --color-border:          #ffffff14; /* hairline borders */
  --color-border-strong:   #ffffff28;
  --color-text-primary:    #e8e6e0;
  --color-text-secondary:  #9b9890;
  --color-text-muted:      #5c5a56;
  --color-accent-amber:    #f59e0b;   /* primary accent */
  --color-accent-emerald:  #10b981;   /* success / active */
  --color-accent-violet:   #8b5cf6;   /* reflecting / planning */
  --color-accent-red:      #ef4444;   /* error */
  --color-accent-slate:    #64748b;   /* idle / neutral */
}
```

### Typography rules
- Body/chrome: `font-sans` (system-ui fallback)
- Agent output, tool args, code: `font-mono`
- Minimum body size: `text-xs` (12px) — never smaller in any element
- No `font-bold` heavier than `font-medium` (500) in chrome elements
- Agent response text renders at `text-sm` (14px), `leading-relaxed`

### Animation rules
- Use Framer Motion `layout` prop for list reordering (tool call cards,
  subagent cards)
- Use CSS `transition` (not Framer Motion) for color/opacity changes ≤ 300ms
- Wrap all `@keyframes` animations in `@media (prefers-reduced-motion: no-preference)`
- No looping decorative animations — all animation conveys state change

### Accessibility
- All interactive elements have visible focus rings (`outline: 2px solid var(--color-accent-amber)`)
- All icon-only buttons have `aria-label`
- The activation grid canvas has `role="img" aria-label="Memory activation grid — {N} active slots"`
- SSE-driven live regions use `aria-live="polite"` on their container

---

## 7. File structure

```
sovereign-ai/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Shell: status bar + sidebar + panels
│   │   ├── globals.css         # Color tokens + Tailwind v4 config
│   │   └── page.tsx            # Default route → terminal pane
│   ├── components/
│   │   ├── shell/
│   │   │   ├── StatusBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── RightPanel.tsx
│   │   ├── panels/
│   │   │   ├── ActivationGrid.tsx   # Canvas 2D panel
│   │   │   ├── ToolInspector.tsx    # Expandable tool call log
│   │   │   ├── SessionTimeline.tsx  # SVG Gantt timeline
│   │   │   ├── ReasoningStream.tsx  # Collapsible CoT panel
│   │   │   ├── MemoryDrawer.tsx     # Slide-in drawer
│   │   │   └── SubagentPanel.tsx    # Subagent cards
│   │   └── ui/                 # shadcn/ui primitives (auto-generated)
│   ├── hooks/
│   │   ├── useSSE.ts           # Generic SSE hook with reconnect
│   │   ├── useTimeline.ts      # Phase segment layout calculator
│   │   ├── useMemoryGrid.ts    # Activation decay + write logic
│   │   └── useToolStream.ts    # Tool call accumulator (create + patch)
│   ├── stores/
│   │   ├── agentStore.ts       # Phase, session, latency, model
│   │   ├── memoryStore.ts      # Slot map + activation levels
│   │   ├── toolStore.ts        # Tool call log (max 50)
│   │   └── subagentStore.ts    # Subagent list
│   └── lib/
│       ├── api.ts              # Typed fetch/SSE wrappers
│       └── utils.ts            # cn(), timeAgo(), formatMs()
├── backend/
│   ├── main.py                 # FastAPI app + all routes
│   ├── pty_handler.py          # WebSocket PTY bridge
│   ├── memory.py               # SQLite memory store
│   ├── sessions.py             # Session management
│   └── subagents.py            # Subagent process manager
├── prisma/
│   └── schema.prisma           # Sessions, memory slots, tool log
├── DECISIONS.md                # Log any library additions here
└── README.md
```

---

## 8. What to build first (priority order)

1. **Shell layout** — status bar, sidebar, right panel tabs, bottom bar.
   No functionality yet, just the grid with placeholder content.
2. **Backend stubs** — all API endpoints returning mocked data so the
   frontend has something to connect to immediately.
3. **`useSSE` hook** — generic, with exponential backoff reconnect. Every
   streaming panel depends on this.
4. **Tool call inspector** — highest information density, most immediately
   useful. Wire to `/api/tools/stream`.
5. **Activation grid** — canvas panel with simulated decay, then wire to
   `/api/memory/activations`.
6. **Session timeline** — SVG layout, zoom slider, stat row.
7. **Reasoning stream** — collapsible, token-by-token.
8. **Memory drawer** — table, sort, search, export/import.
9. **Subagent panel** — polling, mini grids, kill button.
10. **xterm.js terminal pane** — PTY WebSocket, fit addon, custom theme.

---

## 9. Explicit non-goals

Do not build these — they are deliberately out of scope for v1:

- A visual node graph / knowledge graph editor
- WebGL shaders or particle systems
- A model fine-tuning UI
- Voice input/output
- Mobile-responsive layout (desktop-first only; 1280px+ minimum)
- Multi-user / auth beyond the single bearer token

---

## 10. Differentiators from Hermes Agent (enforce these)

Sovereign AI must be meaningfully different in these ways:

| Dimension | Hermes Agent | Sovereign AI |
|---|---|---|
| Primary accent color | Electric blue `#0000f2` | Amber `#f59e0b` |
| Visual language | Cyberpunk dark, branded uppercase | Mission-critical slate, sentence case |
| TUI integration | Ink (React) + Python JSON-RPC | xterm.js WebSocket PTY — no Ink |
| Theme system | 6 built-in themes + YAML overrides | Single coherent dark theme; CSS vars only |
| Memory UI | Implicit (agent manages) | Explicit grid + drawer — user inspects everything |
| Plugin system | Full JS plugin SDK with slots | No plugin system in v1; panels are first-class |
| Upstream branding | "Nous Research · Messenger of the Digital Gods" | No tagline; product speaks for itself |

Every panel header uses sentence case. No uppercase except the product name
`Sovereign` in the sidebar wordmark.

---

*End of brief. Begin with the shell layout (item 1 in §8) and confirm the
directory structure before writing any panel components.*
