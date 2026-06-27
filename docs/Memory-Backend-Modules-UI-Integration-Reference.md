# Memory Backend Modules — Reference Guide for UI Integration

**For**: GLM (Prompt Creator)
**Date**: 2026-06-27
**Purpose**: Explain what each memory module does and how it maps to UI features

---

## Overview

Your Sovereign AI project can support **multiple memory backends simultaneously**. Each backend specializes in a different type of memory query. The user enables/disables backends via Settings. The agent routes queries to the best backend(s) for the job. Results are fused into a single ranked list.

**Key principle**: Not all backends run all queries. A router picks 2-3 relevant backends per query type. This keeps latency low (~65ms total) while maximizing accuracy.

---

## The 7 Memory Types (Cognitive Architecture)

| # | Type | What It Stores | Example Query | Best Backend |
|---|------|---------------|-------------|--------------|
| 1 | **Working** | Active session context, scratchpad, reasoning steps | "What was I just doing?" | In-context (LLM) |
| 2 | **Semantic** | Facts, preferences, domain knowledge | "What IDE does the user prefer?" | Qdrant, Mem0, Cognee |
| 3 | **Episodic** | Past events, task runs, outcomes | "When did I last fix a UI bug?" | SQLite FTS5, Graphiti, Kuzu |
| 4 | **Procedural** | Skills, workflows, learned behaviors | "How do I set up a new worker?" | SkillRegistry, EverOS |
| 5 | **Retrieval** | Documents, code, RAG chunks | "Find the adapter factory code" | Qdrant, Obsidian, SQLite FTS5 |
| 6 | **Prospective** | Future goals, reminders, scheduled tasks | "What did I schedule for tomorrow?" | MonitorDaemon, Cron |
| 7 | **Organizational** | Policies, lineage, certified definitions | "What is the approved naming convention?" | Neo4j, Cognee |

---

## Backend Modules — What Each Does

### 1. SQLite FTS5 (Tier 1 — Always Hot)

**What it does**: Full-text search over all memory entries. Embedded in Python stdlib. Zero configuration. Zero network calls.

**Best for**:
- Exact keyword search ("error code 500")
- Session transcript search ("find all conversations about UI")
- Temporal filtering ("show me entries from last week")
- Fast prefix/suffix matching

**How it works**:
- Every memory write goes to a SQLite table + FTS5 virtual index
- Triggers auto-sync the FTS index on insert/delete
- Query uses `MATCH` syntax with ranking by relevance
- Supports column filtering: `memory_type:semantic scope:session`

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Search panel — keyword input | Primary backend for text queries |
| Memory Search — "exact match" toggle | Forces FTS5 over semantic search |
| Timeline panel — date range filter | FTS5 temporal queries |
| "Find in sessions" | FTS5 with `memory_type:episodic` |

**Visual indicators in UI**:
- Badge: "FTS" on search results that came from this backend
- Status: "✓ Indexed" with entry count in Settings

---

### 2. Kuzu Graph (Tier 1 — Always Hot)

**What it does**: Embedded graph database. Stores memory as nodes (entities) and edges (relationships). Cypher-compatible. File-based.

**Best for**:
- Relationship queries ("what tasks depend on this skill?")
- Multi-hop reasoning ("what did I try before that worked?")
- Memory map visualization (nodes + edges = graph)
- Pathfinding ("show me the path from problem to solution")

**How it works**:
- Every memory entry becomes a node with properties (id, key, type, activation, timestamp)
- `entry.entities` creates edges to related nodes
- Cypher queries traverse the graph: `MATCH (a)-[:RELATES_TO]->(b)`
- Zero server process — reads/writes directly to `.kuzu` file

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Map panel — force-directed graph | **Primary** — renders nodes + edges |
| Memory Map — click node to expand neighbors | Graph traversal query |
| Memory Map — "Show connections" filter | Edge type filtering (`RELATES_TO`, `caused_by`) |
| Memory Search — "related to" queries | Graph traversal fallback |
| Timeline — "What happened before this?" | Temporal edge traversal |

**Visual indicators in UI**:
- Node colors by type (session=blue, task=green, decision=amber, entity=violet, concept=pink, skill=cyan, worker=red)
- Edge labels on hover ("caused by", "depends on", "used skill")
- Glow intensity = activation score
- Graph legend in sidebar

---

### 3. Qdrant Vector (Tier 2 — Warm)

**What it does**: Vector similarity search. Stores embeddings of memory entries. Finds "semantically similar" content even with different keywords.

**Best for**:
- Semantic search ("code like this" even if different words)
- Concept clustering ("group similar tasks")
- Cross-modal retrieval (if you add image embeddings later)
- Fuzzy matching when exact keywords fail

**How it works**:
- Each memory entry gets an embedding vector (via sentence-transformers)
- Stored in Qdrant with HNSW index for fast approximate search
- Query embedding compared to all stored vectors via cosine similarity
- Returns top-k most similar entries

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Search — "semantic similarity" toggle | Primary when enabled |
| Memory Search — "find similar" button on result | Vector search for clicked entry |
| Memory Map — "cluster by similarity" | Vector clustering + graph layout |
| "What else is like this?" | Qdrant query with result embedding |

**Visual indicators in UI**:
- Badge: "Vector" on semantic search results
- Similarity score: "94% match" on result cards
- Settings: model selector ("all-MiniLM-L6-v2", "mpnet-base", etc.)

---

### 4. PostgreSQL Structured (Tier 2 — Warm)

**What it does**: Structured data storage. ACID transactions. JSONB columns. Complex queries with JOINs.

**Best for**:
- Structured memory with schemas (worker configs, task metadata)
- Aggregations ("count tasks by status")
- Complex filtering ("tasks with cost > $5 and status FAILED")
- Relational data that doesn't fit graph or vector models

**How it works**:
- Memory entries stored as JSONB rows
- PostgreSQL GIN indexes on JSONB for fast nested queries
- Full SQL power: JOINs, GROUP BY, window functions

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Workers panel — worker list + metadata | Primary storage for worker records |
| Tasks panel — filtering, sorting | SQL queries with WHERE/ORDER BY |
| Cost Dashboard — aggregations | SQL GROUP BY on cost data |
| Settings — structured config | JSONB storage for user preferences |

**Visual indicators in UI**:
- Badge: "Structured" on results from Postgres
- Settings: "Postgres connected" status with row count

---

### 5. Cognee (Tier 2 — Optional Hybrid)

**What it does**: Open-source graph + vector hybrid. Auto-extracts entities and relationships from text. 14 search modes.

**Best for**:
- Automatic knowledge graph construction from conversations
- Hybrid search (graph traversal + vector similarity in one query)
- Provenance tracking (every fact traces back to source document)
- MCP integration (external tools can query memory)

**How it works**:
- Ingests text → extracts entities → builds graph → stores vectors
- Three stores: Graph (Kuzu/Neo4j) + Vector (LanceDB/Qdrant) + Relational (SQLite/Postgres)
- Search modes: GRAPH_COMPLETION, RAG_COMPLETION, TEMPORAL, CYPHER, etc.
- Default: zero infrastructure (SQLite + LanceDB + Kuzu)

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Search — "smart search" mode | Cognee's auto-selected search mode |
| Memory Map — auto-generated relationships | Cognee entity extraction |
| Settings — "Auto-extract entities" toggle | Cognee pipeline on/off |
| "Why did the agent decide this?" | Cognee provenance query |

**Visual indicators in UI**:
- Badge: "Cognee" with search mode icon (graph, vector, hybrid)
- Settings: extraction confidence slider
- MCP status: "Cognee MCP server running"

---

### 6. Mem0 (Tier 3 — Cloud, Opt-in)

**What it does**: Managed semantic memory API. Drop-in personalization. 90K+ developers.

**Best for**:
- Cross-device memory sync (if you run Sovereign AI on multiple machines)
- Advanced personalization (learns user preferences over time)
- Memory compression (reduces redundant context automatically)
- When you don't want to manage vector DB infrastructure

**How it works**:
- API calls to Mem0 cloud service (or self-hosted)
- Single-call add/get: `mem0.add("User prefers dark mode")`
- Multi-signal retrieval: semantic + keyword + entity matching
- Compression engine deduplicates redundant memories

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Settings — "Cloud memory sync" toggle | Enable/disable Mem0 |
| Memory Search — "include cloud" checkbox | Query Mem0 alongside local backends |
| "User preferences" panel | Mem0 semantic memory display |
| Cross-device session continuity | Mem0 cloud persistence |

**Visual indicators in UI**:
- Badge: "Cloud" with sync status icon
- Settings: API key input, sync frequency selector
- Privacy indicator: "Data stored in Mem0 cloud"

---

### 7. Zep + Graphiti (Tier 3 — Cloud, Opt-in)

**What it does**: Temporal knowledge graph. Every fact has valid/invalid timestamps. Handles changing preferences natively.

**Best for**:
- Temporal reasoning ("What did the user prefer LAST month vs now?")
- Conflict resolution (old facts invalidated, new facts take precedence)
- Enterprise governance (data lineage, audit trails)
- Long-term user modeling with preference drift

**How it works**:
- Graphiti (open-source) builds temporal context graphs
- Zep (managed) handles scale, governance, multi-tenant
- Every entity/edge has `valid_at` and `invalid_at` timestamps
- Query returns facts valid at a specific point in time

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Search — "time travel" slider | Query facts valid at specific date |
| Memory Map — temporal animation | Show graph evolution over time |
| "What changed?" panel | Diff between two time points |
| Settings — "Temporal memory" section | Zep config, retention policies |

**Visual indicators in UI**:
- Timeline slider on Memory Map
- Node border color: solid = current, dashed = expired
- "Valid until" tooltip on hovered nodes

---

### 8. Neo4j (Tier 3 — Server, Opt-in)

**What it does**: Full enterprise graph database. Cypher query language. AuraDB cloud or self-hosted.

**Best for**:
- Large-scale graphs (100K+ nodes)
- Complex analytics (PageRank, community detection, centrality)
- Enterprise deployments with existing Neo4j infrastructure
- Advanced visualization (Bloom)

**UI mapping**:
| UI Feature | Backend Role |
|------------|-------------|
| Memory Map — large dataset mode | Neo4j for >500 nodes |
| Analytics panel — "most connected memory" | Graph algorithms |
| Settings — "Neo4j connection" | URI, username, password |
| Export to Neo4j Bloom | Full visualization in external tool |

**Visual indicators in UI**:
- Settings: connection status, node count, DB size
- "Open in Bloom" button for complex graphs

---

## UI Integration Map

### Which Backends Power Which UI Features?

| UI Panel/Feature | Primary Backend | Secondary Backend(s) | What It Shows |
|-------------------|-----------------|---------------------|---------------|
| **Memory Map** (graph) | Kuzu | Cognee (auto-relationships) | Interactive node-edge graph of all memory |
| **Memory Search** (list) | SQLite FTS5 | Qdrant (semantic), Kuzu (related) | Ranked search results with scores |
| **Memory Timeline** | SQLite FTS5 | Kuzu (temporal edges) | Chronological event stream |
| **Memory Config** | All | — | Backend toggle, health status, entry counts |
| **Worker Detail** | PostgreSQL | Kuzu (connections) | Worker profile + related tasks/skills |
| **Task Detail** | PostgreSQL | SQLite FTS5 (logs), Kuzu (dependencies) | Task metadata + execution history |
| **Cost Dashboard** | PostgreSQL | — | Aggregated cost data |
| **Settings — Preferences** | SQLite FTS5 | Mem0 (if cloud sync) | User preference storage |
| **"Why did agent do this?"** | Cognee | Kuzu (provenance) | Decision trace with source attribution |
| **"Find similar"** | Qdrant | — | Vector similarity results |
| **"What changed?"** | Zep/Graphiti | — | Temporal diff between two time points |

---

## Query Routing — How the Agent Picks Backends

The agent doesn't ask the user "which backend?" per query. It classifies the intent and routes automatically:

| User Query | Intent | Backends Queried | Why |
|------------|--------|-------------------|-----|
| "When did I last work on UI?" | Temporal | Kuzu, SQLite FTS5 | Graph has temporal edges; FTS5 has timestamps |
| "What depends on the memory module?" | Relationship | Kuzu only | Graph traversal is the right tool |
| "Find code like this adapter" | Semantic | Qdrant, SQLite FTS5 | Vector similarity + keyword fallback |
| "Error code 500 in session 8f2a" | Exact | SQLite FTS5 only | Exact match, no need for vectors |
| "Show me my memory map" | Visual | Kuzu only | Graph data for rendering |
| "What did I prefer last month?" | Temporal | Zep/Graphiti, Kuzu | Temporal invalidation + graph |
| "Why did the agent choose D3?" | Provenance | Cognee, Kuzu | Source attribution + decision trace |

---

## Settings UI — Backend Toggle Panel

```
┌─────────────────────────────────────────────┐
│  Memory Backends                            │
│                                             │
│  TIER 1 — Always Hot (Embedded)             │
│  [✓] SQLite FTS5    [✓] Kuzu Graph        │
│      Indexed: 1,247       Nodes: 892        │
│      Status: ✓ Healthy    Status: ✓ Healthy │
│                                             │
│  TIER 2 — Warm (Local Services)             │
│  [✓] Qdrant Vector  [✓] PostgreSQL          │
│      Vectors: 892         Rows: 3,421       │
│      Status: ✓ Healthy    Status: ✓ Healthy │
│  [ ] Cognee Hybrid                          │
│      Auto-extract entities: OFF             │
│      Status: — Not installed                │
│                                             │
│  TIER 3 — Cold (Cloud/External, Opt-in)     │
│  [ ] Mem0 Cloud         [ ] Zep Cloud       │
│      API Key: —           API Key: —        │
│      Status: — Disabled   Status: — Disabled│
│  [ ] Neo4j Server                           │
│      URI: bolt://localhost:7687             │
│      Status: — Not connected                │
│                                             │
│  Query Routing: [Automatic ▼]               │
│    • Automatic (agent picks backends)       │
│    • Manual (ask per query)                 │
│    • Fixed (always use default)             │
│                                             │
│  Default Backend: [SQLite FTS5 ▼]         │
│  Max Results: [10 ▼]                        │
│  Reranking: [✓] Enabled                   │
└─────────────────────────────────────────────┘
```

---

## Visual Backend Indicators in Search Results

Every search result card shows which backend(s) found it:

```
┌─────────────────────────────────────────┐
│  [FTS] [Vector]  Fix UI gaps            │
│  Score: 94.2%  |  Type: task            │
│  Found by: SQLite FTS5 + Qdrant         │
│  Both backends agree → high confidence  │
├─────────────────────────────────────────┤
│  [Graph]  Memory module                 │
│  Score: 87.5%  |  Type: entity           │
│  Found by: Kuzu (3-hop traversal)       │
│  Related to: 12 other nodes             │
└─────────────────────────────────────────┘
```

---

## Performance Expectations

| Operation | Latency | Backends Involved |
|-----------|---------|-------------------|
| Simple keyword search | ~15ms | SQLite FTS5 |
| Semantic search | ~30ms | Qdrant |
| Graph neighbor expansion | ~25ms | Kuzu |
| Hybrid search (3 backends) | ~65ms | FTS5 + Qdrant + Kuzu |
| Full graph render (200 nodes) | ~100ms | Kuzu query + force simulation |
| Memory write (4 backends) | ~20ms | All active (async) |
| Backend health check | ~10ms | All active (parallel) |

---

## Installation Tiers

```bash
# Minimal (Tier 1 only) — what you have now + Kuzu
pip install sovereign-ai
# SQLite FTS5 is built-in, Kuzu is lightweight dependency

# + Local vector + structured (Tier 2)
pip install sovereign-ai[memory-local]
# Adds Qdrant client, psycopg2, Cognee

# + Everything (Tier 3 cloud)
pip install sovereign-ai[memory-all]
# Adds Mem0, Zep, Neo4j drivers
```

---

## Summary for GLM

**What to tell Devin**:

1. **Backend**: Implement the protocol (`MemoryBackend`) and at least SQLite FTS5 + Kuzu. Wrap existing Qdrant and Postgres. Make orchestrator route queries by intent.

2. **API**: Add `/api/memory/search`, `/api/memory/graph`, `/api/memory/health`, `/api/memory/config`. Return fused results with backend attribution.

3. **UI**: Three new panels:
   - **Memory Map** — force-directed graph from Kuzu, colored nodes, clickable, zoom/pan
   - **Memory Search** — unified search box, type filters, results show which backend found them
   - **Memory Config** — toggle backends on/off, see health status, entry counts

4. **Panel module**: `web/static/memory.js` (extend the existing `Memory` object, or create `web/static/memory-map.js` + `web/static/memory-search.js` + `web/static/memory-config.js` as separate panel modules). Each exposes an object with `init()` and `update()` methods — no Zustand store, no React state. Panel state (graph data, search results, selected node, backend status) is held as module-level `let` variables inside the `.js` file. (See `AGENTS.md` AR21b for vanilla JS panel conventions. The original React/Zustand approach using `memoryMapStore.ts` was abandoned with `src/` in commit `c48ce4c` — see `LANDMINES.md` L23, `DECISIONS.md` Decision 11.)

5. **Integration**: Add "Memory Map", "Memory Search", and "Memory Config" entries to the sidebar in `web/static/ui.js` (the `UI.SIDEBAR_ITEMS` array or equivalent). Add `<script>` tags for the new `.js` files in `web/static/index.html`. Add API functions (`searchMemory`, `getMemoryGraph`, `getMemoryHealth`, `getMemoryConfig`, `setMemoryConfig`) to `web/static/api.js` in the `API` object.

**No need for**: Round table review, context brief, 7-step workflow. This is a reference document, not a plan file.
